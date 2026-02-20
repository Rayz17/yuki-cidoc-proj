# 文物文化特征单元数据抽取系统 - 设计方案 V2.0

## 1. 问题分析

### 1.1 当前系统的局限性

#### 问题1：数据库表设计字段不足
**现状**：当前数据库只有7个字段（id, artifact_code, artifact_type, subtype, material_type, process, found_in_tomb），无法存储数据结构模板中定义的22个文化特征单元。

**影响**：大量文物特征信息（如硬度、材料纯度、材料细腻程度、掺杂材料、色泽、器型、纹饰等）无法存储。

#### 问题2：跨文本块的单品信息整合
**现状**：长文本被切块后，同一单品的信息可能分散在多个文本块中，每次LLM调用返回的是独立的结果，没有整合机制。

**影响**：同一文物的信息被重复记录或信息不完整。

#### 问题3：报告与模板的对应关系
**现状**：所有抽取结果存储在同一个表中，无法区分是用哪个模板从哪个报告中抽取的。

**影响**：
- 无法追溯数据来源
- 不同模板的字段混在一起
- 无法支持多模板并行使用

#### 问题4：提示词缺乏通用性
**现状**：提示词硬编码了"陶器、玉器、石器"等特定类型，以及固定的字段列表。

**影响**：更换模板时需要手动修改提示词，无法自动适配不同的数据结构。

---

## 2. 解决方案设计

### 2.1 动态数据库表结构方案

#### 2.1.1 核心思路
采用**动态表创建**策略：根据数据结构模板自动生成对应的数据库表。

#### 2.1.2 表命名规则
```
表名格式: artifacts_{report_id}_{template_id}
示例: artifacts_yaoshanM1_pottery_v1
```

#### 2.1.3 表结构设计

**元数据表（metadata）**：
```sql
CREATE TABLE extraction_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    table_name TEXT UNIQUE,           -- 数据表名
    report_name TEXT,                  -- 报告名称
    report_path TEXT,                  -- 报告路径
    template_name TEXT,                -- 模板名称
    template_path TEXT,                -- 模板路径
    created_at TIMESTAMP,              -- 创建时间
    total_artifacts INTEGER,           -- 文物总数
    extraction_status TEXT             -- 抽取状态
);
```

**动态文物表**：
根据模板的"文化特征单元"列动态生成字段。

**基础字段**（所有表都有）：
- `id`: 自增主键
- `artifact_code`: 单品编码（唯一索引）
- `artifact_type`: 文物类型
- `subtype`: 子类型
- `found_in_tomb`: 出土墓葬
- `extraction_confidence`: 抽取置信度（0-1）
- `source_text_blocks`: 来源文本块ID列表（JSON）

**动态字段**：
从模板的"文化特征单元"列读取，转换为数据库字段名：
```python
# 示例映射
"材料种类" -> material_type
"材料纯度" -> material_purity
"材料细腻程度" -> material_fineness
"掺杂材料" -> mixed_materials
"硬度" -> hardness
"色泽" -> color
"器型" -> vessel_shape
"纹饰" -> decoration
"尺寸" -> dimensions
"工艺" -> process
```

#### 2.1.4 字段类型推断
根据特征单元的性质自动推断字段类型：
- 包含"种类"、"类型"、"器型"等：TEXT
- 包含"程度"、"纯度"等：TEXT（描述性）
- 包含"硬度"、"温度"等：REAL（数值）
- 包含"尺寸"、"直径"、"高度"等：TEXT（保留原文）
- 默认：TEXT

---

### 2.2 单品信息整合方案

#### 2.2.1 核心思路
采用**两阶段抽取**策略：
1. **分块抽取阶段**：对每个文本块独立抽取
2. **信息整合阶段**：按单品编码合并结果

#### 2.2.2 实现流程

```python
# 阶段1: 分块抽取
text_blocks = split_long_text(full_text, max_tokens=2000)
partial_results = []

for block_id, block_text in enumerate(text_blocks):
    artifacts = extract_from_text_with_llm(block_text, template)
    for artifact in artifacts:
        artifact['_source_block_id'] = block_id
        artifact['_source_text'] = block_text[:200]  # 保留片段用于验证
    partial_results.extend(artifacts)

# 阶段2: 信息整合
merged_artifacts = merge_artifacts_by_code(partial_results)
```

#### 2.2.3 合并策略

**规则1：字段值优先级**
- 非空值优先于空值
- 更长的描述优先于更短的描述
- 后出现的数值优先（可能是更精确的测量）

**规则2：冲突处理**
```python
def merge_field_values(values):
    """合并同一字段的多个值"""
    # 过滤空值
    non_null = [v for v in values if v and str(v) != 'null']
    
    if len(non_null) == 0:
        return None
    elif len(non_null) == 1:
        return non_null[0]
    else:
        # 多个非空值：选择最长的描述
        return max(non_null, key=lambda x: len(str(x)))
```

**规则3：来源追踪**
保留所有来源文本块ID：
```python
merged_artifact['source_text_blocks'] = json.dumps([1, 3, 5])
```

---

### 2.3 报告-模板-表对应方案

#### 2.3.1 工作流程

```
用户输入
  ├─ 报告文件: reports/yaoshan_M1.md
  └─ 模板文件: templates/pottery_structure.xlsx

系统处理
  ├─ 生成唯一标识: report_id = "yaoshan_M1", template_id = "pottery_v1"
  ├─ 创建表名: artifacts_yaoshan_M1_pottery_v1
  ├─ 根据模板动态创建表结构
  ├─ 执行抽取
  └─ 记录元数据到 extraction_metadata 表
```

#### 2.3.2 GUI 界面改进

**数据库浏览页面**：
```
┌─────────────────────────────────────────┐
│ 数据库浏览                              │
├─────────────────────────────────────────┤
│ 选择抽取任务:                           │
│ ┌─────────────────────────────────────┐ │
│ │ 瑶山M1 + 陶器模板v1 (2024-12-01)    │ │
│ │ 瑶山M2 + 玉器模板v1 (2024-12-02)    │ │
│ │ 反山M1 + 陶器模板v2 (2024-12-03)    │ │
│ └─────────────────────────────────────┘ │
│                                         │
│ 任务详情:                               │
│ - 报告: reports/yaoshan_M1.md          │
│ - 模板: templates/pottery_v1.xlsx      │
│ - 文物数量: 45                          │
│ - 抽取时间: 2024-12-01 15:30           │
│                                         │
│ [查看数据] [导出CSV] [删除任务]        │
└─────────────────────────────────────────┘
```

---

### 2.4 通用提示词方案

#### 2.4.1 动态提示词生成

**核心思路**：根据模板内容动态生成提示词。

**提示词模板**：
```python
PROMPT_TEMPLATE = """你是一位专业的考古学AI助手。你的任务是从提供的【考古报告文本】中，严格按要求抽取【{artifact_types}】信息。

<核心指令>
- 严格仅输出JSON格式，遵循下方的"输出格式"。
- 不要添加任何前言、解释、代码块或注释。
- 如果某条信息在报告中未提及，请将其值设为 `null`。
- 对于描述性字段，如果原文有明确描述，务必使用原文的完整术语。
- `文物类型` 字段只能是以下之一: {valid_types}。
</核心指令>

<报告原文>
{tomb_text}
</报告原文>

<待抽取字段>
{field_descriptions}
</待抽取字段>

<输出格式>
{output_example}
</输出格式>
"""
```

#### 2.4.2 字段描述生成

从模板自动生成字段描述：
```python
def generate_field_descriptions(template_data):
    """从模板生成字段描述"""
    fields = []
    
    for row in template_data:
        field_name = row['文化特征单元（以陶器为例子）']
        description = row.get('说明/备注', '')
        entity_type = row.get('核心实体类型（Entity）', '')
        
        if field_name and str(field_name) != 'nan':
            fields.append(f"- {field_name}: {description}")
    
    return "\n".join(fields)
```

#### 2.4.3 输出示例生成

自动生成JSON示例：
```python
def generate_output_example(template_data):
    """生成输出示例"""
    example_fields = {}
    
    for row in template_data:
        field_name = row['文化特征单元（以陶器为例子）']
        if field_name and str(field_name) != 'nan':
            example_fields[field_name] = "示例值或null"
    
    return json.dumps({
        "artifacts": [
            {
                "单品编码": "M1:1",
                "文物类型": "陶器",
                **example_fields
            }
        ]
    }, ensure_ascii=False, indent=4)
```

---

## 3. 技术实现方案

### 3.1 新增/修改的模块

#### 3.1.1 `template_analyzer.py`（新增）
**功能**：分析模板结构，提取字段定义

```python
class TemplateAnalyzer:
    def __init__(self, template_path):
        self.template_path = template_path
        self.df = pd.read_excel(template_path)
    
    def get_artifact_types(self):
        """获取文物类型列表"""
        return self.df['文物类型'].dropna().unique().tolist()
    
    def get_feature_fields(self):
        """获取所有文化特征单元字段"""
        column = '文化特征单元（以陶器为例子）'
        fields = self.df[column].dropna().tolist()
        return [f for f in fields if str(f) != 'nan']
    
    def get_field_metadata(self):
        """获取字段元数据（类型、描述等）"""
        metadata = {}
        for _, row in self.df.iterrows():
            field_name = row['文化特征单元（以陶器为例子）']
            if pd.notna(field_name):
                metadata[field_name] = {
                    'description': row.get('说明/备注', ''),
                    'entity_type': row.get('核心实体类型（Entity）', ''),
                    'property': row.get('关系 (Property)', ''),
                    'class': row.get('中间类 (Class)', '')
                }
        return metadata
    
    def generate_db_schema(self):
        """生成数据库表结构"""
        fields = self.get_feature_fields()
        schema = {
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'artifact_code': 'TEXT UNIQUE',
            'artifact_type': 'TEXT',
            'subtype': 'TEXT',
            'found_in_tomb': 'TEXT',
            'extraction_confidence': 'REAL',
            'source_text_blocks': 'TEXT'
        }
        
        # 添加动态字段
        for field in fields:
            db_field_name = self._to_db_field_name(field)
            schema[db_field_name] = 'TEXT'  # 默认TEXT类型
        
        return schema
    
    def _to_db_field_name(self, chinese_name):
        """中文字段名转数据库字段名"""
        mapping = {
            '材料种类': 'material_type',
            '材料纯度': 'material_purity',
            '材料细腻程度': 'material_fineness',
            '掺杂材料': 'mixed_materials',
            '硬度': 'hardness',
            '色泽': 'color',
            '器型': 'vessel_shape',
            '纹饰': 'decoration',
            '尺寸': 'dimensions',
            '工艺': 'process',
            # ... 更多映射
        }
        return mapping.get(chinese_name, 
                          chinese_name.lower().replace(' ', '_'))
```

#### 3.1.2 `prompt_generator.py`（新增）
**功能**：根据模板动态生成提示词

```python
class PromptGenerator:
    def __init__(self, template_analyzer):
        self.analyzer = template_analyzer
    
    def generate_extraction_prompt(self, tomb_text):
        """生成抽取提示词"""
        artifact_types = self.analyzer.get_artifact_types()
        field_metadata = self.analyzer.get_field_metadata()
        
        # 生成字段描述
        field_descriptions = []
        for field_name, metadata in field_metadata.items():
            desc = f"- {field_name}: {metadata['description']}"
            field_descriptions.append(desc)
        
        # 生成输出示例
        example_fields = {field: "null" for field in field_metadata.keys()}
        output_example = json.dumps({
            "artifacts": [
                {
                    "单品编码": "M1:1",
                    "文物类型": artifact_types[0] if artifact_types else "陶器",
                    **example_fields
                }
            ]
        }, ensure_ascii=False, indent=4)
        
        # 填充模板
        prompt = PROMPT_TEMPLATE.format(
            artifact_types="、".join(artifact_types),
            valid_types="、".join(artifact_types),
            tomb_text=tomb_text,
            field_descriptions="\n".join(field_descriptions),
            output_example=output_example
        )
        
        return prompt
```

#### 3.1.3 `database_manager.py`（重构）
**功能**：支持动态表创建和管理

```python
class DynamicDatabaseManager:
    def __init__(self, db_path='database/artifacts.db'):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        self.conn = sqlite3.connect(self.db_path)
    
    def create_metadata_table(self):
        """创建元数据表"""
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS extraction_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                table_name TEXT UNIQUE,
                report_name TEXT,
                report_path TEXT,
                template_name TEXT,
                template_path TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                total_artifacts INTEGER DEFAULT 0,
                extraction_status TEXT DEFAULT 'pending'
            )
        ''')
        self.conn.commit()
    
    def create_artifact_table(self, table_name, schema):
        """根据schema动态创建文物表"""
        cursor = self.conn.cursor()
        
        # 构建CREATE TABLE语句
        fields = []
        for field_name, field_type in schema.items():
            fields.append(f"{field_name} {field_type}")
        
        create_sql = f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                {", ".join(fields)}
            )
        '''
        cursor.execute(create_sql)
        self.conn.commit()
    
    def insert_artifact(self, table_name, artifact_data):
        """插入文物数据"""
        cursor = self.conn.cursor()
        
        # 动态构建INSERT语句
        fields = list(artifact_data.keys())
        placeholders = ['?' for _ in fields]
        values = [artifact_data[f] for f in fields]
        
        insert_sql = f'''
            INSERT OR REPLACE INTO {table_name}
            ({", ".join(fields)})
            VALUES ({", ".join(placeholders)})
        '''
        cursor.execute(insert_sql, values)
        self.conn.commit()
    
    def register_extraction_task(self, table_name, report_info, template_info):
        """注册抽取任务"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO extraction_metadata
            (table_name, report_name, report_path, template_name, template_path)
            VALUES (?, ?, ?, ?, ?)
        ''', (table_name, report_info['name'], report_info['path'],
              template_info['name'], template_info['path']))
        self.conn.commit()
    
    def get_all_tasks(self):
        """获取所有抽取任务"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM extraction_metadata ORDER BY created_at DESC')
        return cursor.fetchall()
```

#### 3.1.4 `artifact_merger.py`（新增）
**功能**：合并跨文本块的单品信息

```python
class ArtifactMerger:
    def merge_by_code(self, artifacts_list):
        """按单品编码合并文物信息"""
        # 按单品编码分组
        grouped = {}
        for artifact in artifacts_list:
            code = artifact.get('单品编码') or artifact.get('artifact_code')
            if not code:
                continue
            
            if code not in grouped:
                grouped[code] = []
            grouped[code].append(artifact)
        
        # 合并每组
        merged_results = []
        for code, group in grouped.items():
            merged = self._merge_group(group)
            merged_results.append(merged)
        
        return merged_results
    
    def _merge_group(self, group):
        """合并同一单品的多条记录"""
        if len(group) == 1:
            return group[0]
        
        merged = {}
        all_fields = set()
        for artifact in group:
            all_fields.update(artifact.keys())
        
        # 合并每个字段
        for field in all_fields:
            values = [a.get(field) for a in group]
            merged[field] = self._merge_field_values(values)
        
        # 记录来源
        source_blocks = []
        for artifact in group:
            if '_source_block_id' in artifact:
                source_blocks.append(artifact['_source_block_id'])
        merged['source_text_blocks'] = json.dumps(source_blocks)
        
        return merged
    
    def _merge_field_values(self, values):
        """合并字段值"""
        # 过滤空值
        non_null = [v for v in values if v and str(v).lower() not in ['null', 'none', 'nan']]
        
        if len(non_null) == 0:
            return None
        elif len(non_null) == 1:
            return non_null[0]
        else:
            # 选择最长的描述
            return max(non_null, key=lambda x: len(str(x)))
```

---

## 4. 实施计划

### 4.1 开发阶段

| 阶段 | 任务 | 预计工作量 |
|------|------|-----------|
| **Phase 1: 基础重构** | | |
| 1.1 | 创建 `template_analyzer.py` | 4小时 |
| 1.2 | 创建 `prompt_generator.py` | 3小时 |
| 1.3 | 重构 `database_manager.py` | 6小时 |
| 1.4 | 创建 `artifact_merger.py` | 4小时 |
| **Phase 2: 核心流程改造** | | |
| 2.1 | 修改 `main.py` 支持动态表创建 | 3小时 |
| 2.2 | 修改 `automated_extractor.py` 使用动态提示词 | 3小时 |
| 2.3 | 实现文本分块和信息整合流程 | 5小时 |
| **Phase 3: GUI 改造** | | |
| 3.1 | 修改数据库浏览界面支持多表 | 4小时 |
| 3.2 | 添加任务管理界面 | 3小时 |
| 3.3 | 改进数据展示（中文字段映射） | 2小时 |
| **Phase 4: 测试与文档** | | |
| 4.1 | 端到端测试 | 4小时 |
| 4.2 | 更新文档和手册 | 2小时 |

**总计**: 约43小时（5-6个工作日）

### 4.2 测试计划

#### 测试用例1：单模板单报告
- 输入：瑶山M1报告 + 陶器模板
- 验证：表结构正确，所有字段都被抽取

#### 测试用例2：多模板多报告
- 输入：
  - 瑶山M1 + 陶器模板
  - 瑶山M1 + 玉器模板
  - 反山M1 + 陶器模板
- 验证：生成3个独立的表，数据不混淆

#### 测试用例3：长文本分块
- 输入：超长报告（>5000字）
- 验证：同一单品的信息被正确合并

#### 测试用例4：新模板适配
- 输入：全新的数据结构模板
- 验证：提示词自动生成，抽取成功

---

## 5. 预期效果

### 5.1 功能提升
1. ✅ 支持任意数据结构模板，无需修改代码
2. ✅ 完整存储所有文化特征单元信息
3. ✅ 正确处理跨文本块的单品信息
4. ✅ 清晰的数据溯源（报告-模板-表对应）
5. ✅ 更友好的多任务管理界面

### 5.2 性能指标
- 模板适配时间：< 1秒
- 长文本处理：支持10000+字的报告
- 信息整合准确率：> 95%
- 数据库查询响应：< 100ms

### 5.3 可扩展性
- 支持新增任意文物类型模板
- 支持自定义字段映射规则
- 支持插件式的合并策略

---

## 6. 风险与应对

### 风险1：LLM输出格式不稳定
**应对**：增强JSON解析的容错性，支持多种格式

### 风险2：字段映射冲突
**应对**：建立完整的中英文映射表，支持手动配置

### 风险3：数据库表过多
**应对**：提供表清理功能，支持归档旧任务

---

*文档版本：V2.0*  
*更新时间：2024-12-01*  
*作者：AI Assistant*

