# 考古文物数据抽取系统架构文档 V3.2

## 1. 系统概览 (System Overview)

本系统旨在从非结构化的考古报告（PDF/Markdown）中，利用 LLM 技术自动化抽取结构化的文物数据。
V3.2 版本引入了**元数据驱动（Meta-Model Driven）**的设计理念，不仅存储文物实体数据，还通过数据库表显式存储“抽取模版”与“CIDOC-CRM 体系”的映射关系，实现了数据、模版、语义的完全解耦与结构化。

---

## 2. 核心架构设计 (Core Architecture)

系统数据存储分为三层：**实体数据层**、**元数据映射层**、**语义事实层**。

### 2.1 实体数据层 (Entity Layer)
*   **用途**：存储核心业务对象（遗址、时期、陶器、玉器）。
*   **特点**：宽表结构，包含常用查询字段（如 `artifact_code`, `dimensions`），用于应用层的快速检索和展示。

### 2.2 元数据映射层 (Meta-Model Layer) **[V3.2 新增]**
*   **用途**：存储 Excel 模版的定义及其与 CIDOC-CRM 的对应关系。
*   **特点**：将“陶土种类”等配置项数据化，不再硬编码在 Python 代码中。

### 2.3 语义事实层 (Semantic Fact Layer) **[V3.2 新增]**
*   **用途**：以纵表（EAV/Triple）形式存储所有抽取到的属性值。
*   **特点**：直接对应知识图谱的边（Edge），解决了“新增模版字段需修改数据库结构”的问题，实现了数据的无限扩展。

---

## 3. 详细数据库设计 (Detailed Schema)

### 3.1 元数据映射层表结构

#### 3.1.1 `sys_template_mappings` (模版映射配置表)
存储 Excel 模版中的每一列是如何定义，以及如何映射到 CIDOC 体系的。

| 字段名 | 类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `id` | INT | 主键 | 1 |
| `artifact_type` | TEXT | 适用文物类型 | 'pottery' |
| `field_name_cn` | TEXT | **模版中的中文列名** | '陶土种类' |
| `field_name_en` | TEXT | 对应的数据库字段名 | 'clay_type' |
| `description` | TEXT | 字段说明（发给LLM） | '识别构成文物材料的基本类型' |
| `cidoc_entity` | TEXT | **CIDOC 主体类型** | 'E22_Man-Made_Object' |
| `cidoc_property` | TEXT | **CIDOC 关系谓词** | 'P45_consists_of' |
| `target_class` | TEXT | **CIDOC 目标类型** | 'E57_Material' |

---

### 3.2 语义事实层表结构

#### 3.2.1 `fact_artifact_triples` (文物语义三元组表)
这是实现知识图谱化的核心表。它将“平面”的文物记录拆解为知识图谱中的“边”。

| 字段名 | 类型 | 说明 | 示例 |
| :--- | :--- | :--- | :--- |
| `id` | INT | 主键 | 1001 |
| `artifact_type` | TEXT | 文物类型 | 'pottery' |
| `artifact_id` | INT | 关联文物ID | 50 (关联 pottery_artifacts.id) |
| `mapping_id` | INT | **关联模版配置** | 1 (关联 sys_template_mappings.id) |
| `predicate` | TEXT | 关系 (冗余字段优化查询) | 'P45_consists_of' |
| `object_value` | TEXT | **抽取到的具体值** | '夹砂红陶' |
| `confidence` | REAL | 置信度 | 0.95 |

---

### 3.3 实体数据层表结构 (完整字段)

#### 3.3.1 `pottery_artifacts` (陶器表)

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | INT | 主键 |
| `task_id` | TEXT | 关联任务ID |
| `site_id` | INT | 关联遗址ID (允许为空) |
| `period_id` | INT | 关联时期ID |
| `structure_id` | INT | 关联遗址结构ID |
| **基础信息** | | |
| `artifact_code` | TEXT | **单品编码** (核心唯一标识) |
| `artifact_type` | TEXT | 默认 '陶器' |
| `subtype` | TEXT | 子类型 (如: 陶鼎) |
| **材料特征** | | |
| `clay_type` | TEXT | 陶土种类 |
| `clay_purity` | TEXT | 陶土纯洁程度 |
| `clay_fineness` | TEXT | 陶土细腻程度 |
| `mixed_materials` | TEXT | 掺和料 |
| **物理特征** | | |
| `hardness` | REAL | 硬度 |
| `color` | TEXT | 颜色/色泽 |
| `surface_treatment` | TEXT | 表面处理 |
| **形制特征** | | |
| `basic_shape` | TEXT | 基本器型 |
| `shape_features` | TEXT | 器型部位特征 |
| `vessel_combination` | TEXT | 器物组合 |
| **尺寸数据** | | |
| `dimensions` | TEXT | 尺寸描述原文 |
| `height` | REAL | 通高 (cm) |
| `diameter` | REAL | 口径 (cm) |
| `thickness` | REAL | 壁厚 (cm) |
| **其他属性** | | |
| `function` | TEXT | 功能 |
| `forming_technique` | TEXT | 成型工艺 |
| `finishing_technique` | TEXT | 修整技术 |
| `decoration_method` | TEXT | 装饰手法 |
| `decoration_type` | TEXT | 纹饰类型 |
| `firing_temperature` | REAL | 烧成温度 |
| `production_activity`| TEXT | 制作活动 |
| `maker` | TEXT | 制作者 |
| `production_date` | TEXT | 制作年代 |
| `production_location`| TEXT | 制作地点 |
| `excavation_location`| TEXT | 原始出土地点 |
| `excavation_activity`| TEXT | 发掘活动 |
| `found_in_tomb` | TEXT | 出土墓葬编号 |
| `preservation_status`| TEXT | 保存状况 |
| `completeness` | TEXT | 完整程度 |
| **扩展数据** | | |
| `raw_attributes` | TEXT | **原始JSON数据** (全量备份) |
| `cidoc_attributes` | TEXT | **语义JSON数据** (结构化备份) |
| `has_images` | BOOL | 是否有关联图片 |
| `main_image_id` | INT | 主图ID |

#### 3.3.2 `jade_artifacts` (玉器表)

*(结构类似陶器表，以下为特有字段)*

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `category_level1` | TEXT | 一级分类 |
| `category_level2` | TEXT | 二级分类 |
| `category_level3` | TEXT | 三级分类 |
| `shape_unit` | TEXT | 器型单元 |
| `shape_description` | TEXT | 形制描述 |
| `decoration_unit` | TEXT | 纹饰单元 |
| `decoration_theme` | TEXT | 纹饰题材 |
| `decoration_description`| TEXT | 纹饰描述 |
| `craft_unit` | TEXT | 工艺特征单元 |
| `cutting_technique` | TEXT | 切割与成型 |
| `drilling_technique` | TEXT | 钻孔技术 |
| `carving_technique` | TEXT | 雕刻技法 |
| `jade_type` | TEXT | 玉料类型 |
| `jade_color` | TEXT | 玉色 |
| `transparency` | TEXT | 透明度 |
| `hole_diameter` | REAL | 孔径 |
| `weight` | REAL | 重量 |

#### 3.3.3 `sites` (遗址表) & `periods` (时期表)
*(保留 V3.0 设计，存储报告层级的宏观信息)*

#### 3.3.4 `extraction_tasks` (任务表) & `images` (图片表)
*(保留 V3.0 设计，用于任务管理和图片索引)*

---

## 4. 抽取与映射工作流 (Extraction & Mapping Logic)

### 4.1 初始化阶段
1.  **模版加载**：系统读取 Excel 模版。
2.  **配置同步**：将模版中的每一行（属性定义、CIDOC信息）写入或更新到 `sys_template_mappings` 表中。这确保了数据库中的配置永远与 Excel 模版保持一致。

### 4.2 抽取阶段
1.  **Prompt 生成**：根据 `sys_template_mappings` 中的 `field_name_cn` 和 `description` 生成提示词。
2.  **LLM 推理**：LLM 返回 JSON，例如 `{"陶土种类": "夹砂", "高度": 15.5}`。

### 4.3 存储阶段 (三级存储)
系统接收到 LLM 的数据后，进行三次写入：

1.  **写入实体表 (Level 1)**：
    *   将常用字段（如高度、颜色）映射并写入 `pottery_artifacts` 的对应列。
    *   目的：支持常规 SQL 查询。

2.  **写入原始 JSON (Level 2)**：
    *   将完整的 LLM 返回结果存入 `pottery_artifacts.raw_attributes`。
    *   目的：数据备份，防止字段映射遗漏。

3.  **写入语义事实表 (Level 3 - Knowledge Graph)**：
    *   遍历抽取到的每个属性（如“陶土种类”）。
    *   在 `sys_template_mappings` 中查找其对应的 CIDOC 定义（E22 -> P45 -> E57）。
    *   在 `fact_artifact_triples` 表中插入一条记录：
        *   Artifact: `Current Artifact ID`
        *   Mapping: `Mapping ID for 陶土种类`
        *   Value: `"夹砂"`
    *   **目的**：完成知识图谱的三元组构建。

---

## 5. 知识图谱应用 (Knowledge Graph Application)

基于 V3.2 架构，构建知识图谱不再需要复杂的转换脚本，只需执行 SQL 查询即可导出标准 RDF 数据：

```sql
-- 导出所有“由...构成” (P45_consists_of) 的关系
SELECT 
    'http://kg.org/artifact/' || p.artifact_code AS Subject,
    m.cidoc_property AS Predicate,
    f.object_value AS Object
FROM fact_artifact_triples f
JOIN pottery_artifacts p ON f.artifact_id = p.id
JOIN sys_template_mappings m ON f.mapping_id = m.id
WHERE m.cidoc_property = 'P45_consists_of';
```

这种设计完美实现了**“模版即图谱定义，抽取即图谱构建”**的目标。
