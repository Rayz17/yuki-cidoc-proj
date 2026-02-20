# CIDOC-CRM 知识图谱实施方案 (V5.0 - 属性扩展版)

本版本在 **V4.0 语义增强版** 的基础上，进一步将 `cidoc-kg-def4.xlsx` 中定义的**所有文化特征单元**及其在各业务数据表中的字段，系统性地映射到图谱中，并为每个特征单元及其二级衍生属性显式建模为节点与关系。

目标是让图谱既完全遵循 CIDOC CRM 的核心语义路径，又提供一套更通用的 **“Attribute / Value” 属性图结构**，方便图计算和后续扩展。

---

## 1. 整体思路概览

### 1.1 三层结构

1. **CIDOC 主干结构（保持 V4 的骨架）**
   - Site–Place–Feature–Artifact–Production–TimeSpan–Period
   - 详见 V4 文档，不再赘述。

2. **文化特征单元层（Feature Unit Layer）**
   - 对应 `cidoc-kg-def4.xlsx` 中的“抽取属性：文化特征单元”，例如：
     - 陶土纯洁程度、陶土细腻程度、掺杂物、器型特征、烧成温度、纹饰主题……
   - 每一个文化特征单元在图中都有一个专门的“特征单元节点”。

3. **二级衍生属性与具体取值层（Metric & Value Layer）**
   - 某些文化特征单元在数据表中进一步拆出多个字段，例如：
     - “量度信息” → 长度/宽度/高度/厚度/直径等二级字段；
     - “颜色” → 主色、次色等。
   - 每一个“二级字段”也建模为节点，挂在对应的“特征单元节点”下面；
   - 每一个具体字段值（数值 / 文本）则建模为“值节点”，与二级属性节点关联。

### 1.2 双重语义通路

对于任意一个文物（如一件陶器），它的一个属性（例如“陶土纯洁程度=较高”）会在图里表现为两条路径：

1. **CIDOC 语义路径**（若在 `cidoc-kg-def4` 中有定义）：
   - `E22_Man-Made_Object` --P2 / P45 / P43 / P108→ 中间类 / 范围类节点
   - 例如：`E22` →P2→ `E55_Type("高纯度")`

2. **属性图路径**（Attribute Graph）：
   - `E22_Man-Made_Object` -[:HAS_FEATURE]-> `FU_陶土纯洁程度`
   - `FU_陶土纯洁程度` -[:HAS_VALUE]-> `VAL_高纯度`

对于有二级衍生字段的情况（如“量度信息”）：

- `E22` -[:HAS_FEATURE]-> `FU_量度信息`
- `FU_量度信息` -[:HAS_METRIC]-> `FM_高度`
- `FM_高度` -[:HAS_VALUE]-> `VAL_11.3` （数值或文本）

这样既可以走 CIDOC 路径做“语义推理”，也可以走 HAS_FEATURE / HAS_METRIC / HAS_VALUE 做更通用的“属性值聚类”和数值分析。

---

## 2. V5 图模型设计

### 2.1 核心 CIDOC 节点与关系（继承 V4）

沿用 V4 的定义（见 `NEO4J_IMPLEMENTATION_V4.md`）：

- 节点：`E27_Site`、`E53_Place`、`E25_Man_Made_Feature`、`E22_Man_Made_Object`、`E12_Production`、`E52_Time_Span`、`E4_Period`、`E55_Type`、`E57_Material`。
- 关系：
  - `E27_Site -[:P46_is_composed_of]-> E53_Place`
  - `E53_Place -[:P46_is_composed_of]-> E53_Place`
  - `E25_Man_Made_Feature -[:P89_falls_within]-> E53_Place`
  - `E25_Man_Made_Feature -[:P89_falls_within]-> E27_Site`（快捷路径）
  - `E22_Man_Made_Object -[:P53_has_former_or_current_location]-> E25_Man_Made_Feature`
  - `E22_Man_Made_Object -[:P108i_was_produced_by]-> E12_Production`
  - `E12_Production -[:P32_used_general_technique]-> E55_Type`
  - `E12_Production -[:P4_has_time_span]-> E52_Time_Span`
  - `E12_Production -[:P10_falls_within]-> E4_Period`
  - `E25_Man_Made_Feature -[:P108i_was_produced_by]-> E12_Production`
  - `E4_Period -[:P7_took_place_at]-> E27_Site`
  - `E22_Man_Made_Object -[:P45_consists_of]-> E57_Material`
  - `E22_Man_Made_Object -[:P2_has_type]-> E55_Type`

### 2.2 新增：文化特征单元与属性图节点

| 标签 (Label) | 说明 | 关键属性 | ID 规则 |
| :--- | :--- | :--- | :--- |
| **`FeatureUnit`** | 文化特征单元（一级） | `name`（来自 def4，如“陶土纯洁程度”）、`domain`(`E22`/`E27`…)、`cidoc_property`、`cidoc_range` | `fu_{md5(domain+name)}` |
| **`FeatureMetric`** | 二级衍生属性（某特征下的字段） | `name`（如“高度(cm)”）、`parent_unit` | `fm_{md5(unit+name)}` |
| **`FeatureValue`** | 具体取值节点 | `raw`（原文）、`numeric`（可选）、`unit`（可选）、`value_type` | `fv_{md5(metric+raw)}` |

对应新增关系：

| 起点 | 关系类型 | 终点 | 说明 |
| :--- | :--- | :--- | :--- |
| `FeatureMetric` | `HAS_METRIC_OF` | `FeatureUnit` | 二级属性从属于特征单元 |
| `E22_Man_Made_Object` | `HAS_FEATURE` | `FeatureUnit` | 某件文物具有该特征单元 |
| `E22_Man_Made_Object` | `HAS_METRIC` | `FeatureMetric` | 某件文物具有该具体衍生属性 |
| `FeatureUnit` | `HAS_VALUE` | `FeatureValue` | 特征单元上的某种取值（无二级属性时） |
| `FeatureMetric` | `HAS_VALUE` | `FeatureValue` | 二级衍生属性的取值节点 |

> 说明：  
> - 当某文化特征单元在 CSV 中仅有一个字段（无二级拆分）时，直接创建 `FeatureUnit` + `FeatureValue`：  
>   `Artifact -[:HAS_FEATURE]-> FeatureUnit -[:HAS_VALUE]-> FeatureValue`。  
> - 当该特征单元有多个二级字段时（如长宽高），则：
>   `Artifact -[:HAS_FEATURE]-> FeatureUnit` +  
>   `FeatureMetric -[:HAS_METRIC_OF]-> FeatureUnit` +  
>   `Artifact -[:HAS_METRIC]-> FeatureMetric` +  
>   `FeatureMetric -[:HAS_VALUE]-> FeatureValue`。

### 2.3 文化特征单元与 CIDOC 的桥接

为了保持 def4 的 CIDOC 语义，`FeatureUnit` 本身会携带或关联到 CIDOC 路径信息：

- 属性形式：
  - `FeatureUnit.cidoc_domain`（如 `"E22_Man-Made_Object"`）
  - `FeatureUnit.cidoc_property`（如 `"P2_has_type"`）
  - `FeatureUnit.cidoc_intermediate`（如 `"E12_Production"` 或空）
  - `FeatureUnit.cidoc_range`（如 `"E55_Type"`）

这样在分析时，可以：

- 只用 `HAS_FEATURE/HAS_METRIC/HAS_VALUE` 做“属性图”分析；
- 也可以结合 `cidoc_*` 元数据，将某类 `FeatureUnit` 映射回标准 CIDOC 语义路径。

---

## 3. 基于 `cidoc-kg-def4.xlsx` 的通用映射流程

### 3.1 规则与字段映射加载

1. **加载 def4 规则表**
   - 使用 `pandas.read_excel('for-neo4j/cidoc-kg-def4.xlsx')`，选取如下列：
     - `文物类型` (object_type)
     - `核心实体（Domain）` (domain_label)
     - `关系 (Property)` (property)
     - `中间类 (Class)` (intermediate_class)
     - `子属性 (Sub-Property)` (sub_property)
     - `目标类 (Range Class)` (range_class)
     - `抽取属性：文化特征单元` (feature_unit_name)
   - 构建字典：
     ```python
     unit_rules[(domain_label, feature_unit_name)] = {
         "property": property,
         "intermediate": intermediate_class or None,
         "sub_property": sub_property or None,
         "range": range_class
     }
     ```

2. **加载字段↔特征单元映射**
   - 建议维护一个 `docs/TEMPLATE_DB_MAPPING.csv`，列如：
     - `table_name`（如 `pottery_artifacts_export_20251203`）
     - `column_name`（如 `陶土纯洁度`、`高度(cm)`）
     - `feature_unit`（如 `陶土纯洁程度`、`量度信息`）
     - `sub_metric`（可为空，如 `高度(cm)` / `长度(cm)` 等）
   - 构建映射：
     ```python
     field_to_unit[(table_name, column_name)] = (feature_unit, sub_metric)
     ```

3. **预生成 FeatureUnit / FeatureMetric 节点**
   - 遍历所有 `(domain_label, feature_unit)` 组合：  
     为每一个生成 `FeatureUnit` 节点；
   - 遍历所有 `(feature_unit, sub_metric)` 组合：  
     为每一个生成 `FeatureMetric` 节点，并建立 `FeatureMetric -[:HAS_METRIC_OF]-> FeatureUnit`。

### 3.2 行级映射：对每个文物应用规则

在 V4 的 `process_artifact(row, cat_label)` 末尾增加：

```python
def apply_cidoc_and_feature_units(artifact_id, row, table_name, domain_label="E22_Man-Made_Object"):
    for col_name, value in row.items():
        if pd.isna(value) or str(value).strip() == "":
            continue
        key = (table_name, col_name)
        if key not in field_to_unit:
            continue
        unit_name, sub_metric = field_to_unit[key]
        rule = unit_rules.get((domain_label, unit_name))
        if not rule:
            # 该特征单元在 def4 中未定义 CIDOC 路径，仍然可以只走属性图路径
            emit_attribute_graph_only(artifact_id, unit_name, sub_metric, value)
        else:
            emit_by_rule(artifact_id, unit_name, sub_metric, value, rule)
```

其中：

- `emit_attribute_graph_only` 负责只建：
  - `Artifact -[:HAS_FEATURE]-> FeatureUnit`
  - （若有 sub_metric）`Artifact -[:HAS_METRIC]-> FeatureMetric`
  - `FeatureUnit/FeatureMetric -[:HAS_VALUE]-> FeatureValue`
- `emit_by_rule` 在上述基础上，再根据 rule 扩展 **CIDOC 路径**：
  - 模式 A：无中间类，生成 `E55/E57` 概念节点 + `P2/P45` 等；
  - 模式 B：有中间类（E12/E54/E52 等），生成/复用事件或量度节点，并建立对应 P 关系。

### 3.3 具体生成逻辑示例

#### 3.3.1 示例 1：陶土纯洁程度（无二级指标）

- def4 规则：  
  Domain=`E22`，Property=`P2 has type`，Range=`E55_Type`，文化特征单元=`陶土纯洁程度`
- 源表：`pottery_artifacts_export_20251203.陶土纯洁度 = "高纯度"`

生成：

1. **CIDOC 路径**
   - `Type` 节点：`E55_Type(name="高纯度")`
   - 边：`(artifact:E22)-[:P2_has_type]->(type:E55_Type)`

2. **属性图路径**
   - `FeatureUnit`: `FU_陶土纯洁程度`
   - `FeatureValue`: `VAL_高纯度`
   - `(artifact)-[:HAS_FEATURE]->(FU_陶土纯洁程度)`
   - `(FU_陶土纯洁程度)-[:HAS_VALUE]->(VAL_高纯度)`

#### 3.3.2 示例 2：量度信息（含高度/直径等二级指标）

- def4 规则：  
  Domain=`E22`，Property=`P43 has dimension`，Intermediate=`E54_Dimension`，文化特征单元=`量度信息`
- 源表：  
  - `高度(cm)=11.3`  
  - `直径(cm)=21.2`

生成：

1. **CIDOC 路径**
   - 对每一个二级字段（高度/直径）创建 `E54_Dimension` 节点，如：
     - `Dim_Height`：`{kind:"高度", value:11.3, unit:"cm"}`
     - `Dim_Diameter`：`{kind:"直径", value:21.2, unit:"cm"}`
   - 边：`(artifact/E12)-[:P43_has_dimension]->(Dim_Height)` 等。

2. **属性图路径**
   - `FeatureUnit`: `FU_量度信息`
   - `FeatureMetric`: `FM_高度(cm)`、`FM_直径(cm)`
   - `FeatureValue`: `VAL_11.3`、`VAL_21.2`
   - 关系：
     - `(artifact)-[:HAS_FEATURE]->(FU_量度信息)`
     - `(FM_高度)-[:HAS_METRIC_OF]->(FU_量度信息)`
     - `(artifact)-[:HAS_METRIC]->(FM_高度)`
     - `(FM_高度)-[:HAS_VALUE]->(VAL_11.3)`

---

## 4. 导出与导入

### 4.1 导出 CSV

在 V4 的基础上新增以下 CSV：

- `nodes_feature_units.csv`（所有 `FeatureUnit`）
- `nodes_feature_metrics.csv`（所有 `FeatureMetric`）
- `nodes_feature_values.csv`（所有 `FeatureValue`）
- `edges_feature_structure.csv`（`HAS_METRIC_OF`）
- `edges_feature_links.csv`（`HAS_FEATURE` / `HAS_METRIC`）
- `edges_feature_values.csv`（`HAS_VALUE`）

### 4.2 Cypher 导入脚本扩展

在 `import_script.cypher` 中新增：

```cypher
// 节点
LOAD CSV WITH HEADERS FROM 'file:///nodes_feature_units.csv' AS row
MERGE (u:FeatureUnit {id: row.id})
SET u.name = row.name,
    u.domain = row.domain,
    u.cidoc_domain = row.cidoc_domain,
    u.cidoc_property = row.cidoc_property,
    u.cidoc_range = row.cidoc_range;

LOAD CSV WITH HEADERS FROM 'file:///nodes_feature_metrics.csv' AS row
MERGE (m:FeatureMetric {id: row.id})
SET m.name = row.name;

LOAD CSV WITH HEADERS FROM 'file:///nodes_feature_values.csv' AS row
MERGE (v:FeatureValue {id: row.id})
SET v.raw = row.raw,
    v.numeric = toFloat(row.numeric),
    v.unit = row.unit;

// 结构关系
LOAD CSV WITH HEADERS FROM 'file:///edges_feature_structure.csv' AS row
MATCH (m:FeatureMetric {id: row.START_ID})
MATCH (u:FeatureUnit {id: row.END_ID})
MERGE (m)-[:HAS_METRIC_OF]->(u);

// 文物 <-> 特征/度量 关系
LOAD CSV WITH HEADERS FROM 'file:///edges_feature_links.csv' AS row
MATCH (a:E22_Man_Made_Object {id: row.START_ID})
MATCH (t {id: row.END_ID})   // t 为 FeatureUnit 或 FeatureMetric
CALL apoc.create.relationship(a, row.TYPE, {}, t) YIELD rel RETURN count(rel);

// 特征/度量 <-> 取值 关系
LOAD CSV WITH HEADERS FROM 'file:///edges_feature_values.csv' AS row
MATCH (s {id: row.START_ID})
MATCH (v:FeatureValue {id: row.END_ID})
MERGE (s)-[:HAS_VALUE]->(v);
```

---

## 5. 小结

V5 在 V4 CIDOC 主干的基础上，增加了三层能力：

1. **文化特征单元显式节点化**：每个 def4 中的特征单元都有对应的 `FeatureUnit`；
2. **二级衍生属性与数值节点化**：每个量度/子属性有 `FeatureMetric` 与 `FeatureValue`；
3. **双通路语义**：既可走 CIDOC 的 P 关系，也可走 `HAS_FEATURE / HAS_METRIC / HAS_VALUE` 这套通用属性图关系。

这样一来，无论是做严格的 CIDOC 语义查询，还是做面向属性的聚类、相似度计算与可视化分析，图谱都具备足够的信息与灵活度。接下来只需要在 `convert_to_graph_v5.py` 中按本方案补全 ETL 逻辑，即可生成完整的 V5 图数据。 


