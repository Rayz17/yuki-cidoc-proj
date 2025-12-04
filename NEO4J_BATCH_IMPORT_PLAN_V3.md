# CIDOC-CRM 知识图谱批量导入与实施方案 (V3.0)

## 1. 方案背景与目标

本方案旨在基于 CIDOC CRM (v7.x) 标准，将 2025年12月3日导出的一批 CSV 数据（遗址、结构、时期、陶器、玉器）转换为 Neo4j 图数据库支持的格式，并实现批量导入。

**核心目标：**
1.  **标准化映射**：严格遵循 CIDOC CRM 定义，将扁平表格数据转换为 "实体-事件-概念" 的语义网络。
2.  **高性能导入**：生成符合 `neo4j-admin import` 标准的 CSV 文件，支持千万级数据量的快速初始化。
3.  **图计算就绪**：构建优化的图结构，支持跨遗址比较、时空分布分析等复杂图算法。

---

## 2. 数据源说明

输入数据位于 `for-neo4j/` 目录：

| 文件名 | 内容描述 | 关键字段 | 预估量级 |
| :--- | :--- | :--- | :--- |
| `sites_export_20251203.csv` | 遗址基础信息 | `ID`, `遗址名称`, `地理坐标` | ~10 |
| `site_structures_export_20251203.csv` | 遗址内结构/单位 | `site_id`, `structure_name`(M12), `structure_type` | ~100+ |
| `periods_export_20251203.csv` | 考古学文化时期 | `site_id`, `时期名称`(良渚文化), `起始时间` | ~50 |
| `pottery_artifacts_export_20251203.csv` | 陶器文物 | `文物编号`, `器型`, `陶土类型`, `出土单位` | ~5000+ |
| `jade_artifacts_export_20251203.csv` | 玉器文物 | `文物编号`, `一级分类`, `玉料类型`, `纹饰单元` | ~3000+ |

---

## 3. 图模型设计 (Graph Schema)

### 3.1 核心节点 (Nodes)

为了兼顾语义准确性和查询性能，我们设计以下核心节点类型：

| 标签 (Label) | CIDOC 类 | 语义说明 | 属性 (Properties) | ID 生成规则 |
| :--- | :--- | :--- | :--- | :--- |
| **`E27_Site`** | E27 Site | 考古遗址 | `name` (遗址名称), `location` | `site_{site_id}` |
| **`E53_Place`** | E53 Place | 较大的地理区域/分区 | `name` (反山墓地), `type` | `place_{hash(name+site_id)}` |
| **`E25_Man_Made_Feature`** | E25 Man-Made Feature | 具体遗迹单位 (墓葬/灰坑) | `name` (M12), `code` | `feat_{hash(name+site_id)}` |
| **`E22_Man_Made_Object`** | E22 Man-Made Object | 出土文物 (陶/玉) | `name` (文物编号), `category` | `obj_{hash(文物编号)}` |
| **`E4_Period`** | E4 Period | 考古学时期 | `name` (良渚文化), `date_range` | `period_{hash(name+site_id)}` |
| **`E55_Type`** | E55 Type | 类型/概念 (器型/纹饰/工艺) | `name` (豆, 刻划, 兽面纹) | `type_{hash(name)}` |
| **`E57_Material`** | E57 Material | 材质 | `name` (夹砂红陶, 软玉) | `mat_{hash(name)}` |

### 3.2 核心关系 (Relationships)

| 关系类型 (Type) | 起始节点 (:START_ID) | 目标节点 (:END_ID) | CIDOC 语义 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| **`P46_is_composed_of`** | E27_Site | E53_Place | 遗址包含区域 | 如：反山遗址 -> 反山墓地 |
| **`P46_is_composed_of`** | E53_Place | E25_Man_Made_Feature | 区域包含单位 | 如：反山墓地 -> M12 |
| **`P89_falls_within`** | E25_Man_Made_Feature | E27_Site | 单位位于遗址内 | (跨层级直接关联，方便查询) |
| **`P53_has_former_or_current_location`** | E22_Man_Made_Object | E25_Man_Made_Feature | 文物出土于 | 如：M12:98 -> M12 |
| **`P2_has_type`** | E22_Man_Made_Object | E55_Type | 文物类型 | 如：M12:98 -> 玉琮 |
| **`P45_consists_of`** | E22_Man_Made_Object | E57_Material | 文物材质 | 如：M12:98 -> 透闪石软玉 |
| **`P108i_was_produced_by`** | E22_Man_Made_Object | E12_Production | 生产事件 | (可选，用于挂载工艺信息) |
| **`P32_used_general_technique`** | E12_Production | E55_Type | 使用工艺 | 生产 -> 轮制 |
| **`P7_took_place_at`** | E4_Period | E27_Site | 时期发生于 | 良渚文化 -> 反山 |
| **`P10_falls_within`** | E22_Man_Made_Object | E4_Period | 文物属于时期 | M12:98 -> 良渚中期 |

---

## 4. 数据转换策略 (Python ETL)

我们将编写 Python 脚本 `convert_to_graph_v3.py` 执行以下转换逻辑：

### 4.1 ID 生成策略
使用 MD5 哈希生成全局唯一 ID，确保多次运行结果一致，且支持增量更新。
```python
def get_id(prefix, value):
    if not value: return None
    clean_val = str(value).strip()
    return f"{prefix}_{hashlib.md5(clean_val.encode('utf-8')).hexdigest()[:8]}"
```

### 4.2 遗址与结构层级处理
*   **源数据**：`site_structures_export`
*   **逻辑**：
    1.  读取 `structure_type`。
    2.  若类型为 `['墓地', '发掘区', '居住区']` -> 映射为 **`E53_Place`**。
    3.  若类型为 `['墓葬', '灰坑', '房址', '井']` -> 映射为 **`E25_Man_Made_Feature`**。
    4.  构建 `Site -> E53` 和 `Site -> E25` 的层级关系。

### 4.3 文物关联逻辑
*   **源数据**：陶器/玉器表
*   **位置关联**：使用 `出土单位` (如 "M12") 或 `出土墓葬` 字段。
    *   查找 `nodes_features` 中名为 "M12" 且属于同一遗址的节点 ID。
    *   建立 `P53` 关系。
*   **类型/材质抽取**：
    *   从 `器型`/`一级分类` 字段提取 **Type**。
    *   从 `陶土类型`/`玉料类型` 字段提取 **Material**。
    *   自动去重并生成 `nodes_concepts.csv`。

---

## 5. 输出文件定义 (CSV Headers)

脚本将生成以下文件用于 Neo4j 导入：

### 5.1 节点文件 (Nodes)
1.  **`nodes_sites.csv`**
    *   `id:ID,name,location,:LABEL`
2.  **`nodes_places.csv`** (E53)
    *   `id:ID,name,type,:LABEL`
3.  **`nodes_features.csv`** (E25)
    *   `id:ID,name,code,type,:LABEL`
4.  **`nodes_periods.csv`**
    *   `id:ID,name,start_date,end_date,:LABEL`
5.  **`nodes_artifacts.csv`**
    *   `id:ID,name,category,height:float,diameter:float,:LABEL`
6.  **`nodes_concepts.csv`**
    *   `id:ID,name,concept_type,:LABEL` (动态 Label 如 E55_Type)

### 5.2 关系文件 (Edges)
1.  **`edges_hierarchy.csv`** (包含 Site-Place, Place-Feature, Site-Period)
    *   `:START_ID,:END_ID,:TYPE`
2.  **`edges_artifact_core.csv`** (包含 Artifact-Feature, Artifact-Period)
    *   `:START_ID,:END_ID,:TYPE`
3.  **`edges_artifact_attributes.csv`** (包含 Artifact-Type, Artifact-Material)
    *   `:START_ID,:END_ID,:TYPE`

---

## 6. Neo4j 导入操作指南

### 步骤 1: 生成 CSV
```bash
# 确保在 venv 环境下
python for-neo4j/convert_to_graph_v3.py
```
产物将位于 `neo4j_import_v3/` 目录。

### 步骤 2: 执行导入 (neo4j-admin)
**注意**：此操作需停止 Neo4j 服务，并会覆盖现有数据库（建议新建数据库）。

```bash
# 假设 Neo4j 安装在 /var/lib/neo4j
NEO4J_HOME="/var/lib/neo4j"
IMPORT_DIR="neo4j_import_v3"

$NEO4J_HOME/bin/neo4j-admin database import full \
    --nodes=$IMPORT_DIR/nodes_sites.csv \
    --nodes=$IMPORT_DIR/nodes_places.csv \
    --nodes=$IMPORT_DIR/nodes_features.csv \
    --nodes=$IMPORT_DIR/nodes_periods.csv \
    --nodes=$IMPORT_DIR/nodes_artifacts.csv \
    --nodes=$IMPORT_DIR/nodes_concepts.csv \
    --relationships=$IMPORT_DIR/edges_hierarchy.csv \
    --relationships=$IMPORT_DIR/edges_artifact_core.csv \
    --relationships=$IMPORT_DIR/edges_artifact_attributes.csv \
    --overwrite-destination neo4j
```

### 步骤 3: 创建索引 (启动后执行)
进入 Neo4j Browser 执行：
```cypher
CREATE INDEX artifact_name FOR (n:E22_Man_Made_Object) ON (n.name);
CREATE INDEX feature_name FOR (n:E25_Man_Made_Feature) ON (n.name);
CREATE INDEX type_name FOR (n:E55_Type) ON (n.name);
```

---

## 7. 图计算应用场景示例

### 7.1 跨遗址相似度计算 (Node Similarity)
**目标**：找出出土文物组合最相似的两个墓葬。
**算法**：Jaccard Similarity / Cosine Similarity
**Cypher 预处理**：
```cypher
// 构建 墓葬-[:HAS_TYPE]->器型 的投影图
MATCH (tomb:E25_Man_Made_Feature)<-[:P53_has_former_or_current_location]-(art:E22_Man_Made_Object)-[:P2_has_type]->(type:E55_Type)
RETURN tomb.name as item, collect(id(type)) as categories
```
**GDS 库调用**：
```cypher
CALL gds.nodeSimilarity.stream({
  nodeProjection: ['E25_Man_Made_Feature', 'E55_Type'],
  relationshipProjection: {
    HAS_TYPE: {
      type: 'HAS_TYPE',
      orientation: 'UNDIRECTED'
    }
  }
})
YIELD node1, node2, similarity
RETURN gds.util.asNode(node1).name AS Tomb1, gds.util.asNode(node2).name AS Tomb2, similarity
ORDER BY similarity DESC
LIMIT 10
```

### 7.2 核心器物组合挖掘 (Louvain Community Detection)
**目标**：发现经常一起出现的器物类型（如“鼎簋组合”）。
**思路**：构建 `Type -[CO_OCCUR]- Type` 关系图，权重为共现次数，运行 Louvain 社区发现算法。

---

## 8. 附录：CIDOC 命名空间缩写对照

*   `E4`: Period (时期)
*   `E12`: Production (生产)
*   `E22`: Man-Made Object (人造物/文物)
*   `E25`: Man-Made Feature (人造特征/遗迹)
*   `E27`: Site (遗址)
*   `E53`: Place (地点)
*   `E55`: Type (类型)
*   `E57`: Material (材质)
*   `P2`: has type
*   `P45`: consists of
*   `P46`: is composed of
*   `P53`: has former or current location
*   `P108`: was produced by

