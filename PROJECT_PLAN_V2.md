# 文物文化特征单元数据抽取系统 - 项目计划 V2.0

## 1. 项目目标（更新）

创建一个**通用化、可扩展**的考古文物信息抽取系统，支持：
1. **任意数据结构模板**：自动适配不同的文化特征单元定义
2. **多报告多模板并行**：清晰的数据溯源和管理
3. **智能信息整合**：正确处理跨文本块的单品信息
4. **动态数据库结构**：根据模板自动生成表结构

---

## 2. 系统架构（V2.0）

```
┌─────────────────────────────────────────────────────────────┐
│                        用户界面层                            │
│  ┌──────────────┐              ┌──────────────┐            │
│  │   CLI接口    │              │   GUI接口    │            │
│  │  (main.py)   │              │   (app.py)   │            │
│  └──────┬───────┘              └──────┬───────┘            │
└─────────┼──────────────────────────────┼──────────────────┘
          │                              │
┌─────────┴──────────────────────────────┴──────────────────┐
│                      核心业务层                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │           工作流编排 (workflow.py) [NEW]           │   │
│  │  - 任务创建  - 文本分块  - 信息整合  - 结果存储   │   │
│  └───┬────────────────────────────────────────────┬───┘   │
│      │                                            │       │
│  ┌───▼──────────┐  ┌──────────────┐  ┌──────────▼────┐  │
│  │模板分析器    │  │提示词生成器  │  │文物信息合并器 │  │
│  │[NEW]         │  │[NEW]         │  │[NEW]          │  │
│  │template_     │  │prompt_       │  │artifact_      │  │
│  │analyzer.py   │  │generator.py  │  │merger.py      │  │
│  └──────────────┘  └──────────────┘  └───────────────┘  │
└─────────┬──────────────────────────────────┬─────────────┘
          │                                  │
┌─────────▼──────────────────────────────────▼─────────────┐
│                      服务层                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │LLM API服务   │  │文本处理服务  │  │数据库服务    │   │
│  │automated_    │  │content_      │  │database_     │   │
│  │extractor.py  │  │extractor.py  │  │manager.py    │   │
│  │              │  │              │  │[重构]        │   │
│  └──────────────┘  └──────────────┘  └──────────────┘   │
└───────────────────────────────────────────────────────────┘
```

---

## 3. 核心改进点

### 3.1 动态数据库表结构
**Before**:
```sql
CREATE TABLE artifacts (
    id, artifact_code, artifact_type, 
    subtype, material_type, process, found_in_tomb
)  -- 仅7个字段，信息丢失严重
```

**After**:
```sql
-- 元数据表
CREATE TABLE extraction_metadata (
    id, table_name, report_name, template_name, 
    created_at, total_artifacts, ...
)

-- 动态文物表（根据模板生成）
CREATE TABLE artifacts_yaoshan_pottery_v1 (
    id, artifact_code, artifact_type, subtype,
    material_type, material_purity, material_fineness,
    mixed_materials, hardness, color, vessel_shape,
    decoration, dimensions, process, ...  -- 22+字段
)
```

### 3.2 智能信息整合
**Before**:
```python
# 每个文本块独立抽取，结果直接存储
for block in text_blocks:
    artifacts = extract(block)
    db.insert(artifacts)  # 可能重复或不完整
```

**After**:
```python
# 两阶段处理
partial_results = []
for block in text_blocks:
    artifacts = extract(block)
    artifacts['_source_block'] = block_id
    partial_results.extend(artifacts)

# 按单品编码合并
merged = merger.merge_by_code(partial_results)
db.insert(merged)
```

### 3.3 通用提示词生成
**Before**:
```python
# 硬编码提示词
prompt = """抽取陶器、玉器、石器...
字段：材料种类、工艺、尺寸..."""
```

**After**:
```python
# 动态生成
analyzer = TemplateAnalyzer(template_path)
generator = PromptGenerator(analyzer)
prompt = generator.generate(tomb_text)
# 自动适配模板中定义的所有字段
```

### 3.4 多任务管理
**Before**:
```
所有数据混在一个表 → 无法区分来源
```

**After**:
```
GUI显示:
├─ 瑶山M1 + 陶器模板v1 (45件文物)
├─ 瑶山M1 + 玉器模板v1 (12件文物)
└─ 反山M1 + 陶器模板v2 (38件文物)
   每个任务独立表，清晰溯源
```

---

## 4. 开发计划

### Phase 1: 基础模块开发（第1-2天）

| 任务ID | 任务描述 | 文件 | 状态 |
|--------|---------|------|------|
| P1.1 | 创建模板分析器 | `src/template_analyzer.py` | 🔲 待开发 |
| P1.2 | 创建提示词生成器 | `src/prompt_generator.py` | 🔲 待开发 |
| P1.3 | 创建文物信息合并器 | `src/artifact_merger.py` | 🔲 待开发 |
| P1.4 | 重构数据库管理器 | `src/database_manager.py` | 🔲 待开发 |

**验收标准**:
- ✅ 模板分析器能正确解析Excel模板
- ✅ 提示词生成器能生成完整的JSON格式提示词
- ✅ 合并器能正确处理重复单品
- ✅ 数据库管理器能动态创建表

### Phase 2: 核心流程改造（第3-4天）

| 任务ID | 任务描述 | 文件 | 状态 |
|--------|---------|------|------|
| P2.1 | 创建工作流编排器 | `src/workflow.py` | 🔲 待开发 |
| P2.2 | 改造主脚本 | `src/main.py` | 🔲 待开发 |
| P2.3 | 更新LLM抽取器 | `src/automated_extractor.py` | 🔲 待开发 |
| P2.4 | 优化文本分块 | `src/content_extractor.py` | 🔲 待开发 |

**验收标准**:
- ✅ 支持指定报告+模板进行抽取
- ✅ 自动生成唯一表名
- ✅ 长文本正确分块和合并
- ✅ 所有字段都被抽取

### Phase 3: GUI改造（第5天）

| 任务ID | 任务描述 | 文件 | 状态 |
|--------|---------|------|------|
| P3.1 | 添加任务管理界面 | `gui/app.py` | 🔲 待开发 |
| P3.2 | 改进数据浏览界面 | `gui/app.py` | 🔲 待开发 |
| P3.3 | 添加任务详情页面 | `gui/app.py` | 🔲 待开发 |
| P3.4 | 优化中文显示 | `gui/app.py` | 🔲 待开发 |

**验收标准**:
- ✅ 能查看所有抽取任务
- ✅ 能选择任务查看详情
- ✅ 所有字段显示中文名称
- ✅ 支持导出完整数据

### Phase 4: 测试与文档（第6天）

| 任务ID | 任务描述 | 状态 |
|--------|---------|------|
| P4.1 | 单模板单报告测试 | 🔲 待测试 |
| P4.2 | 多模板多报告测试 | 🔲 待测试 |
| P4.3 | 长文本分块测试 | 🔲 待测试 |
| P4.4 | 新模板适配测试 | 🔲 待测试 |
| P4.5 | 更新用户手册 | 🔲 待完成 |
| P4.6 | 更新API文档 | 🔲 待完成 |

---

## 5. 测试用例

### 测试用例1：基础功能测试
```bash
# 输入
python src/main.py \
  -r reports/yaoshan_M1.md \
  -t templates/pottery_structure.xlsx

# 预期输出
✅ 创建表: artifacts_yaoshan_M1_pottery_v1
✅ 抽取45件文物
✅ 所有22个字段都有数据
✅ 元数据表记录正确
```

### 测试用例2：多任务并行
```bash
# 任务1
python src/main.py -r reports/yaoshan_M1.md -t templates/pottery_v1.xlsx

# 任务2
python src/main.py -r reports/yaoshan_M1.md -t templates/jade_v1.xlsx

# 任务3
python src/main.py -r reports/fanshan_M1.md -t templates/pottery_v1.xlsx

# 预期输出
✅ 生成3个独立的表
✅ 数据不混淆
✅ GUI能正确显示3个任务
```

### 测试用例3：长文本处理
```bash
# 输入：10000字的报告
python src/main.py -r reports/long_report.md -t templates/pottery_v1.xlsx

# 预期输出
✅ 文本被分成5个块
✅ 同一单品的信息被正确合并
✅ source_text_blocks字段记录来源
```

### 测试用例4：新模板适配
```bash
# 创建全新的模板: stone_tools_v1.xlsx
# 包含新字段: 石材类型、打制方式、刃部形态

python src/main.py -r reports/test.md -t templates/stone_tools_v1.xlsx

# 预期输出
✅ 自动识别新字段
✅ 提示词包含新字段描述
✅ 抽取结果包含所有新字段
```

---

## 6. 文件结构（更新后）

```
yuki-cidoc-proj/
├── src/
│   ├── main.py                    # [修改] CLI入口
│   ├── workflow.py                # [新增] 工作流编排
│   ├── template_analyzer.py       # [新增] 模板分析
│   ├── prompt_generator.py        # [新增] 提示词生成
│   ├── artifact_merger.py         # [新增] 信息合并
│   ├── database_manager.py        # [重构] 数据库管理
│   ├── automated_extractor.py     # [修改] LLM抽取
│   ├── content_extractor.py       # [优化] 文本分块
│   └── report_processor.py        # [保持] 报告处理
├── gui/
│   └── app.py                     # [重构] Streamlit GUI
├── database/
│   └── artifacts.db               # [扩展] 多表结构
├── templates/                     # 数据结构模板
│   ├── pottery_structure_v1.xlsx
│   ├── jade_structure_v1.xlsx
│   └── stone_structure_v1.xlsx
├── reports/                       # 考古报告
│   ├── yaoshan_M1.md
│   └── fanshan_M1.md
├── prompts/
│   └── prompt_template.txt        # [修改] 通用模板
├── config.json                    # 配置文件
├── requirements.txt               # 依赖列表
├── DESIGN_V2.md                   # [新增] 设计文档V2
├── PROJECT_PLAN_V2.md             # [新增] 项目计划V2
├── MANUAL_V2.md                   # [待创建] 用户手册V2
└── README.md                      # 项目说明
```

---

## 7. 关键指标

### 7.1 功能完整性
- [ ] 支持任意模板（100%兼容性）
- [ ] 完整字段覆盖（22/22字段）
- [ ] 信息整合准确率（>95%）
- [ ] 多任务并行支持（无限制）

### 7.2 性能指标
- [ ] 模板解析时间：< 1秒
- [ ] 提示词生成时间：< 0.5秒
- [ ] 单个文本块抽取：< 30秒
- [ ] 信息合并时间：< 1秒/100条
- [ ] 数据库查询：< 100ms

### 7.3 用户体验
- [ ] GUI响应流畅（< 200ms）
- [ ] 中文界面完整
- [ ] 错误提示清晰
- [ ] 操作步骤简化（< 5步完成抽取）

---

## 8. 风险管理

| 风险 | 影响 | 概率 | 应对措施 |
|------|------|------|---------|
| LLM输出格式不稳定 | 高 | 中 | 增强JSON解析容错性 |
| 字段映射冲突 | 中 | 低 | 建立完整映射表 |
| 数据库表过多 | 低 | 高 | 提供清理和归档功能 |
| 长文本超时 | 高 | 中 | 优化分块策略，增加重试 |
| 模板格式不统一 | 中 | 中 | 提供模板验证工具 |

---

## 9. 里程碑

### Milestone 1: 核心功能完成（第1-4天）
- ✅ 所有新模块开发完成
- ✅ 核心流程改造完成
- ✅ 单元测试通过

### Milestone 2: GUI改造完成（第5天）
- ✅ 任务管理界面完成
- ✅ 数据浏览优化完成
- ✅ 集成测试通过

### Milestone 3: 系统上线（第6天）
- ✅ 所有测试用例通过
- ✅ 文档更新完成
- ✅ 用户验收通过

---

## 10. 后续优化方向

### 10.1 短期（1-2周）
- [ ] 添加抽取进度显示
- [ ] 支持批量任务
- [ ] 优化LLM调用成本
- [ ] 添加数据验证规则

### 10.2 中期（1-2月）
- [ ] 支持图片识别（OCR）
- [ ] 添加数据可视化
- [ ] 支持协同标注
- [ ] 导出多种格式（Excel, JSON, XML）

### 10.3 长期（3-6月）
- [ ] 知识图谱构建
- [ ] 智能推荐系统
- [ ] 多语言支持
- [ ] 云端部署

---

*文档版本：V2.0*  
*更新时间：2024-12-01*  
*状态：待开发*

