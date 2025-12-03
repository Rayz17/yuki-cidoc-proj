# 考古文物数据抽取系统 V3.0 - 使用手册

## 系统概述

本系统是一个基于大语言模型（LLM）的考古文物信息自动抽取系统，支持从考古报告中抽取遗址、时期、陶器、玉器四大主体的详细信息，并自动关联图片。

### V3.0 新特性

- ✅ **多主体抽取**：支持遗址、时期、陶器、玉器四类实体
- ✅ **关系管理**：自动建立主体间的关联关系
- ✅ **图片索引**：自动索引和关联文物图片
- ✅ **信息合并**：智能合并跨文本块的同一文物信息
- ✅ **模板驱动**：根据Excel模板动态生成抽取提示词
- ✅ **完整工作流**：从报告到数据库的全自动流程

## 环境准备

### 1. 安装依赖

```bash
# 创建虚拟环境（推荐）
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 或 venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置LLM服务

编辑 `config.json` 文件：

```json
{
  "provider": "coze",
  "api_url": "https://api.coze.cn",
  "bot_id": "your_bot_id",
  "api_key": "your_api_key",
  ...
}
```

支持的provider:
- `coze`: Coze.cn Agent
- `gemini`: Google Gemini API
- `anthropic`: Anthropic Claude API

### 3. 初始化数据库

```bash
python src/main_v3.py --init-db --report "任意报告路径" --pottery-template "任意模板"
```

或手动执行：

```bash
sqlite3 database/artifacts_v3.db < database/schema_v3.sql
```

## 使用方法

### 命令行模式（CLI）

#### 基础用法

```bash
python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"
```

#### 完整抽取（推荐）

```bash
python src/main_v3.py \
  --report "遗址出土报告/瑶山2021修订版解析" \
  --site-template "抽取模版/数据结构3-遗址属性和类分析1129.xlsx" \
  --period-template "抽取模版/数据结构4-时期属性和类分析1129.xlsx" \
  --pottery-template "抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx" \
  --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"
```

#### 参数说明

- `--report`: 报告文件夹路径（必需）
  - 需包含 `full.md`（报告正文）
  - 需包含 `images/` 文件夹（图片）
  - 可选：`*_content_list.json`（内容索引）

- `--pottery-template`: 陶器抽取模板
- `--jade-template`: 玉器抽取模板
- `--site-template`: 遗址抽取模板
- `--period-template`: 时期抽取模板

- `--db`: 数据库路径（默认：`database/artifacts_v3.db`）
- `--report-name`: 报告名称（默认使用文件夹名）
- `--init-db`: 初始化数据库

### 图形界面模式（GUI）

```bash
streamlit run gui/app.py
```

然后在浏览器中访问 `http://localhost:8501`

#### GUI功能

1. **配置管理**
   - 查看和修改LLM配置
   - 支持多种LLM服务

2. **数据抽取**
   - 选择报告和模板
   - 一键启动抽取
   - 实时查看进度

3. **数据浏览**
   - 查看抽取结果
   - 按主体类型筛选
   - 查看文物图片
   - 导出CSV

## 报告文件夹结构

```
遗址出土报告/
└── 瑶山2021修订版解析/
    ├── full.md                          # 报告正文（必需）
    ├── layout.json                      # 布局信息（可选）
    ├── xxx_content_list.json           # 内容索引（可选）
    └── images/                          # 图片文件夹（必需）
        ├── hash1.jpg
        ├── hash2.jpg
        └── ...
```

## 抽取模板说明

模板是Excel文件（.xlsx），定义了要抽取的字段：

### 模板结构

| 文化特征单元 | 说明/备注 | 核心实体类型 | 关系 | 中间类 |
|------------|---------|------------|-----|-------|
| 材料种类    | 识别材料类型 | E22 | P45 | E57 |
| 器型特征    | 描述器型 | E22 | P43 | E55 |
| ...        | ...     | ...  | ... | ... |

### 四类模板

1. **陶器模板**：陶土、器型、工艺、尺寸等
2. **玉器模板**：玉料、分类、纹饰、工艺等
3. **遗址模板**：位置、面积、文化、年代等
4. **时期模板**：时期划分、特征、年代等

## 数据库结构

### 主要表

- `extraction_tasks`: 抽取任务
- `sites`: 遗址信息
- `site_structures`: 遗址结构（自关联）
- `periods`: 时期信息
- `pottery_artifacts`: 陶器文物
- `jade_artifacts`: 玉器文物
- `images`: 图片索引
- `artifact_images`: 文物-图片关联

### 查询示例

```sql
-- 查询某遗址的所有玉器
SELECT j.* FROM jade_artifacts j
JOIN sites s ON s.id = j.site_id
WHERE s.site_name = '瑶山遗址';

-- 查询某文物的所有图片
SELECT i.* FROM images i
JOIN artifact_images ai ON ai.image_id = i.id
WHERE ai.artifact_code = 'M12:1';

-- 查询某时期的文物统计
SELECT 
  p.period_name,
  COUNT(DISTINCT pa.id) as pottery_count,
  COUNT(DISTINCT ja.id) as jade_count
FROM periods p
LEFT JOIN pottery_artifacts pa ON pa.period_id = p.id
LEFT JOIN jade_artifacts ja ON ja.period_id = p.id
GROUP BY p.id;
```

## 工作流程

### 完整流程

```
1. 创建任务
   ↓
2. 索引图片（扫描images文件夹）
   ↓
3. 抽取遗址信息（报告前5000字）
   ↓
4. 抽取时期信息（报告中部）
   ↓
5. 按墓葬分块
   ↓
6. 逐块抽取陶器/玉器
   ↓
7. 合并同一文物信息
   ↓
8. 关联图片
   ↓
9. 保存到数据库
   ↓
10. 生成报告
```

### 信息合并策略

当同一文物在多个文本块中被描述时：

1. **识别**：通过 `artifact_code` 识别同一文物
2. **合并**：
   - 数值字段：取最大值（更精确）
   - 文本字段：取最长的
   - 描述字段：合并所有信息
3. **置信度**：可选择基于置信度的合并

### 图片关联策略

1. **精确匹配**：文物编号出现在图片说明附近
2. **内容匹配**：文物关键词（器型、材质等）匹配
3. **墓葬匹配**：同一墓葬的图片（低置信度）

## 高级功能

### 1. 自定义模板

创建新的Excel模板：

1. 第一列：文化特征单元（字段名）
2. 其他列：说明、实体类型、关系等
3. 系统会自动：
   - 生成英文字段名
   - 推断数据类型
   - 生成数据库表
   - 生成LLM提示词

### 2. 批量抽取

```bash
# 批量处理多个报告
for report in 遗址出土报告/*/; do
  python src/main_v3.py \
    --report "$report" \
    --jade-template "抽取模版/数据结构2-玉器文化特征单元分析1129.xlsx"
done
```

### 3. 导出数据

```python
import sqlite3
import pandas as pd

conn = sqlite3.connect('database/artifacts_v3.db')

# 导出玉器数据
df = pd.read_sql('SELECT * FROM jade_artifacts', conn)
df.to_excel('玉器数据.xlsx', index=False)

# 导出带图片的文物
df = pd.read_sql('''
  SELECT 
    j.*,
    GROUP_CONCAT(i.image_path) as images
  FROM jade_artifacts j
  LEFT JOIN artifact_images ai ON ai.artifact_id = j.id AND ai.artifact_type = 'jade'
  LEFT JOIN images i ON i.id = ai.image_id
  GROUP BY j.id
''', conn)
df.to_excel('玉器数据_含图片.xlsx', index=False)
```

## 故障排查

### 1. 数据库错误

```bash
# 重新初始化数据库
rm database/artifacts_v3.db
python src/main_v3.py --init-db --report "..." --jade-template "..."
```

### 2. LLM调用失败

- 检查 `config.json` 配置
- 检查API密钥是否有效
- 检查网络连接
- 查看日志：`SELECT * FROM extraction_logs WHERE log_level = 'ERROR'`

### 3. 图片关联失败

- 确保 `images/` 文件夹存在
- 确保有 `*_content_list.json` 文件
- 检查图片文件名是否为哈希值

### 4. 信息抽取不完整

- 检查模板字段是否完整
- 检查LLM提示词是否合理
- 尝试调整文本分块大小
- 查看抽取日志

## 性能优化

### 1. 提高抽取速度

- 使用更快的LLM服务
- 减少文本分块数量
- 并行处理多个墓葬

### 2. 提高抽取质量

- 优化模板字段定义
- 提供更详细的字段说明
- 使用更强大的LLM模型
- 增加上下文信息

### 3. 减少成本

- 使用本地LLM
- 缓存LLM响应
- 只抽取必要的主体

## 开发文档

### 核心模块

- `database_manager_v3.py`: 数据库管理
- `image_manager.py`: 图片索引
- `template_analyzer.py`: 模板分析
- `prompt_generator.py`: 提示词生成
- `artifact_merger.py`: 信息合并
- `image_linker.py`: 图片关联
- `workflow.py`: 工作流编排

### 扩展开发

参考 `DESIGN_V2.md` 和 `DATABASE_DESIGN_V3_FINAL.md`

## 常见问题

**Q: 支持哪些文物类型？**  
A: 目前支持陶器和玉器，可通过添加模板扩展到其他类型。

**Q: 可以修改数据库结构吗？**  
A: 可以，修改 `database/schema_v3.sql` 后重新初始化。

**Q: 如何提高图片关联准确率？**  
A: 确保报告中有 `content_list.json`，并且图片说明清晰。

**Q: 支持多语言吗？**  
A: 目前主要支持中文，可通过修改提示词支持其他语言。

**Q: 如何备份数据？**  
A: 直接复制 `database/artifacts_v3.db` 文件。

## 联系与支持

- 查看完整设计文档：`DESIGN_V2.md`、`DATABASE_DESIGN_V3_FINAL.md`
- 查看实施计划：`IMPLEMENTATION_PLAN.md`
- 查看项目计划：`PROJECT_PLAN_V2.md`

---

**版本**: V3.0  
**更新时间**: 2024-12-01

