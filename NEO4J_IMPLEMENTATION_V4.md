# CIDOC-CRM 知识图谱实施方案 (V4.0 - 语义增强版)

## 1. 方案背景与目标

本方案基于 V3.0 方案升级，旨在构建一个**高语义精度、符合 CIDOC CRM (v7.x) 学术标准**的考古知识图谱。

**核心调整：**
1.  **语义增强**：吸纳 Gemini 方案 (方案B) 的细致语义，引入 E12 Production (生产事件)、E54 Dimension (量度)、P108 等深层 CIDOC 关系，不再单纯追求扁平化。
2.  **严格空间层级**：修正 V3 中“Feature 直连 Site”的简化处理，强制实施 **`E25 Feature -[P89]-> E53 Place -[P89]-> E27 Site`** 的严格空间嵌套逻辑。
3.  **健壮 ID 策略**：采用“类型前缀 + MD5(核心属性组合)”的生成策略，确保跨遗址、跨批次数据的唯一性与可合并性。
4.  **灵活导入**：不再强制依赖 `neo4j-admin import`，而是生成标准 Cypher 脚本或分块 CSV，支持用户通过 Cypher Shell 分批灵活导入，优先保证逻辑正确性而非极致导入速度。

---

## 2. 图模型设计 (Graph Schema)

### 2.1 核心节点 (Nodes)

| 标签 (Label) | CIDOC 类 | 语义说明 | 关键属性 | ID 生成规则 |
| :--- | :--- | :--- | :--- | :--- |
| **`E27_Site`** | E27 Site | 遗址本体 | `name` (遗址名), `location` | `site_{md5(name)}` |
| **`E53_Place`** | E53 Place | 空间区域/分区 | `name` (区域名), `type` | `place_{md5(site_id+name)}` |
| **`E25_Man_Made_Feature`** | E25 Man-Made Feature | 遗迹单位 (墓/坑) | `name` (M12), `code`, `type` | `feat_{md5(site_id+name)}` |
| **`E22_Man_Made_Object`** | E22 Man-Made Object | 文物实体 | `name` (编号), `category` | `obj_{md5(编号+site_id)}` |
| **`E12_Production`** | E12 Production | 生产事件 (虚拟) | `note` (制作活动) | `prod_{md5(obj_id)}` |
| **`E4_Period`** | E4 Period | 考古学时期 | `name` (文化期), `date` | `period_{md5(name)}` |
| **`E55_Type`** | E55 Type | 通用类型概念 | `name` (豆, 兽面纹) | `type_{md5(name)}` |
| **`E57_Material`** | E57 Material | 材质概念 | `name` (软玉) | `mat_{md5(name)}` |

### 2.2 核心关系 (Relationships) - 语义增强版

| 领域 (Domain) | 关系 (Property) | 范围 (Range) | 语义/业务逻辑 | 变更说明 |
| :--- | :--- | :--- | :--- | :--- |
| **E27_Site** | `P46_is_composed_of` | **E53_Place** | 遗址由区域组成 | 保持 V3 |
| **E53_Place** | `P46_is_composed_of` | **E53_Place** | 大区域包含小区域 | 新增递归层级 |
| **E25_Man_Made_Feature** | `P89_falls_within` | **E53_Place** | 单位位于区域内 | **修正 V3** (原直连 Site) |
| **E25_Man_Made_Feature** | `P89_falls_within` | **E27_Site** | 单位位于遗址内 | 保留作为快捷路径 (可选) |
| **E22_Man_Made_Object** | `P53_has_former_or_current_location` | **E25_Man_Made_Feature** | 文物出土于单位 | 保持 V3 |
| **E22_Man_Made_Object** | `P108i_was_produced_by` | **E12_Production** | 文物由...生产 | **新增** (引入事件实体) |
| **E12_Production** | `P32_used_general_technique` | **E55_Type** | 生产用了...工艺 | **新增** (挂载工艺) |
| **E12_Production** | `P4_has_time_span` | **E4_Period** | 生产发生于...时期 | **新增** (替代 Artifact直连Period) |
| **E22_Man_Made_Object** | `P45_consists_of` | **E57_Material** | 文物由...材质构成 | 保持 V3 |
| **E22_Man_Made_Object** | `P2_has_type` | **E55_Type** | 文物属于...器型 | 保持 V3 |

---

## 3. 数据转换策略 (Python ETL)

我们将编写 Python 脚本 `convert_to_graph_v4.py`，逻辑如下：

### 3.1 ID 策略 (增强版)
```python
def get_id(prefix, *parts):
    """生成复合键 Hash ID，确保唯一性"""
    raw = "_".join([str(p).strip() for p in parts if pd.notna(p)])
    if not raw: return None
    return f"{prefix}_{hashlib.md5(raw.encode('utf-8')).hexdigest()[:8]}"
```
*   **Artifact ID**: `get_id("obj", site_id, artifact_code)` —— 防止不同遗址有相同编号 "M1:1"。
*   **Feature ID**: `get_id("feat", site_id, feature_name)` —— 防止不同遗址有相同单位 "M1"。

### 3.2 空间层级重建 (Strict Hierarchy)
*   **逻辑**：
    1.  读取 `site_structures.csv`。
    2.  利用 `parent_id` 字段重建树状结构。
    3.  如果 `structure_type` 是 "墓地/区域" -> `E53 Place`。
    4.  如果 `structure_type` 是 "墓葬/灰坑" -> `E25 Feature`。
    5.  **关键链接**：建立 `Child -> Parent` 的引用。
        *   若 Parent 是 Place: 建立 `P89_falls_within` (空间包含)。
        *   若 Parent 也是 Feature (如墓葬中的棺椁): 建立 `P46_is_composed_of` (结构组成)。

### 3.3 生产事件抽取 (Event Extraction)
*   **逻辑**：对于每一件文物，**强制生成一个对应的 `E12_Production` 节点**。
*   **原因**：CIDOC 中，"制作年代"、"制作工艺"、"制作者" 都是 `Production` 事件的属性，而不是 `Object` 的直接属性。
*   **转换**：
    *   CSV `工艺` -> `E12 -[:P32]-> E55(工艺)`
    *   CSV `时期` -> `E12 -[:P4]-> E4(时期)`

---

## 4. 输出产物 (Cypher Import Scripts)

为了最大化兼容性和可调试性，脚本将生成 **Cypher 语句文件 (.cyp)** 而非纯 CSV。用户可以在 Neo4j Browser 或 Cypher Shell 中运行。

### 文件结构
1.  `01_nodes_spatial.cyp`: 创建 Site, Place, Feature 节点。
2.  `02_nodes_concepts.cyp`: 创建 Type, Material, Period 节点。
3.  `03_nodes_artifacts.cyp`: 创建 Artifact 节点。
4.  `04_nodes_events.cyp`: 创建 Production 事件节点。
5.  `05_edges_spatial.cyp`: 建立 P46/P89 空间关系。
6.  `06_edges_production.cyp`: 建立 Artifact -> Production -> Type/Period 关系。
7.  `07_edges_properties.cyp`: 建立 Artifact -> Material/Type 属性关系。

### Cypher 模板示例
```cypher
// 创建生产事件并关联工艺
MATCH (obj:E22_Man_Made_Object {id: 'obj_abc123'})
MERGE (prod:E12_Production {id: 'prod_abc123'})
MERGE (obj)-[:P108i_was_produced_by]->(prod)
WITH prod
MATCH (tech:E55_Type {name: '轮制'})
MERGE (prod)-[:P32_used_general_technique]->(tech);
```

---

## 5. 执行指南

### 步骤 1: 生成数据
运行脚本：
```bash
python for-neo4j/convert_to_graph_v4.py
```
脚本将在 `neo4j_import_v4/` 目录下生成一系列 `.csv` 文件（用于承载数据）和 `import.cypher`（用于执行逻辑）。

### 步骤 2: 导入 Neo4j
使用 Cypher Shell 分块导入（推荐）：

```bash
# 1. 将生成的 csv 放入 neo4j import 目录
cp neo4j_import_v4/*.csv $NEO4J_HOME/import/

# 2. 运行 Cypher Shell
cypher-shell -u neo4j -p password -f neo4j_import_v4/import_script.cypher
```

---

## 6. 方案优势总结

1.  **学术严谨性**：引入 `E12 Production` 事件节点，符合 CIDOC CRM 对 "非物质特征（如年代、工艺）需通过事件关联" 的核心定义。
2.  **空间逻辑完备**：修正了 V3 的简化逻辑，能够支持 "遗址-发掘区-探方-墓葬" 的多级空间查询。
3.  **数据完整性**：通过复合主键生成 ID，彻底解决了跨遗址数据合并时的 ID 冲突风险。
4.  **调试友好**：基于 Cypher 的导入方式，让每一条数据的去向都清晰可见，方便查错和逻辑微调。

