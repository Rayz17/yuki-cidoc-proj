# CIDOC-CRM 知识图谱分析与计算指南 (V5.0 - 属性扩展版)

本指南基于 **V5 属性扩展版图谱结构**，在 V4 的 CIDOC 语义骨架之上，引入 `FeatureUnit / FeatureMetric / FeatureValue` 三类节点与 `HAS_FEATURE / HAS_METRIC / HAS_METRIC_OF / HAS_VALUE` 关系，提供面向**文化特征单元**的图计算查询示例。  

> 前提条件：
> 1. 已使用 `neo4j_import_v5/import_script_v5.cypher` 成功导入 V5 图谱；
> 2. Neo4j 已安装 **APOC** 与 **Graph Data Science (GDS)** 插件（中心度 / 相似度 / 社区发现示例用到）。

---

## 1. V5 数据模型速览

### 1.1 主干 CIDOC 结构（继承 V4）

- 节点：`E27_Site`、`E53_Place`、`E25_Man_Made_Feature`、`E22_Man_Made_Object`、`E12_Production`、`E52_Time_Span`、`E4_Period`、`E55_Type`、`E57_Material`。
- 关系（只列出核心）：
  - `E27_Site -[:P46_is_composed_of]-> E53_Place`
  - `E53_Place -[:P46_is_composed_of]-> E53_Place`
  - `E25_Man_Made_Feature -[:P89_falls_within]-> E53_Place`
  - `E25_Man_Made_Feature -[:P89_falls_within]-> E27_Site`
  - `E22_Man_Made_Object -[:P53_has_former_or_current_location]-> E25_Man_Made_Feature`
  - `E22_Man_Made_Object -[:P108i_was_produced_by]-> E12_Production`
  - `E12_Production -[:P32_used_general_technique]-> E55_Type`
  - `E12_Production -[:P4_has_time_span]-> E52_Time_Span`
  - `E12_Production -[:P10_falls_within]-> E4_Period`
  - `E4_Period -[:P7_took_place_at]-> E27_Site`
  - `E22_Man_Made_Object -[:P45_consists_of]-> E57_Material`
  - `E22_Man_Made_Object -[:P2_has_type]-> E55_Type`

### 1.2 属性图结构（V5 新增）

- 节点：
  - `FeatureUnit`：文化特征单元（如“陶土纯洁程度”“量度信息”“纹饰单元”），属性：
    - `id`, `name`, `domain`, `cidoc_domain`, `cidoc_property`, `cidoc_intermediate`, `cidoc_range`
  - `FeatureMetric`：二级衍生字段（如“高度(cm)”“纹饰主题”），属性：
    - `id`, `name`
  - `FeatureValue`：具体取值节点，属性：
    - `id`, `raw`, `numeric`, `unit`
- 关系：
  - `(:FeatureMetric)-[:HAS_METRIC_OF]->(:FeatureUnit)`
  - `(:E22_Man_Made_Object)-[:HAS_FEATURE]->(:FeatureUnit)`
  - `(:E22_Man_Made_Object)-[:HAS_METRIC]->(:FeatureMetric)`
  - `(:FeatureUnit)-[:HAS_VALUE]->(:FeatureValue)`
  - `(:FeatureMetric)-[:HAS_VALUE]->(:FeatureValue)`

> 例：  
> - 陶器高度：  
>   `(:E22 {name:'M22:61'})-[:HAS_METRIC]->(:FeatureMetric {name:'高度(cm)'})-[:HAS_VALUE]->(:FeatureValue {numeric:15.5})`  
> - 玉器纹饰主题：  
>   `(:E22 {name:'M12:98'})-[:HAS_METRIC]->(:FeatureMetric {name:'纹饰主题'})-[:HAS_VALUE]->(:FeatureValue {raw:'神人兽面纹'})`

---

## 2. 节点中心度分析 (Centrality)

### 2.1 场景 A：最常被使用的文化特征单元 (FeatureUnit)

**问题**：哪些文化特征单元在整体图谱中最“核心”（被最多文物使用）？

```cypher
// 按使用频次统计 FeatureUnit
MATCH (art:E22_Man_Made_Object)-[:HAS_FEATURE]->(fu:FeatureUnit)
RETURN fu.name               AS FeatureUnitName,
       fu.domain             AS Domain,
       fu.cidoc_property     AS CidocProperty,
       fu.cidoc_range        AS CidocRange,
       count(DISTINCT art)   AS ArtifactCount
ORDER BY ArtifactCount DESC, FeatureUnitName
LIMIT 30;
```

### 2.2 场景 B：基于 HAS_FEATURE 的“度中心性”（无需 GDS）

如果当前 Neo4j 实例尚未安装 GDS，可以直接用关系数量近似“中心度”，统计每个 FeatureUnit 关联到多少件文物。

```cypher
// 使用 HAS_FEATURE 关系统计每个 FeatureUnit 被多少文物使用
MATCH (fu:FeatureUnit)
OPTIONAL MATCH (art:E22_Man_Made_Object)-[:HAS_FEATURE]->(fu)
WITH fu, count(DISTINCT art) AS degree
RETURN fu.name    AS FeatureUnitName,
       fu.domain  AS Domain,
       degree     AS ArtifactCount
ORDER BY ArtifactCount DESC, FeatureUnitName
LIMIT 20;
```

---

## 3. 相似度计算 (Similarity)

### 3.1 场景 A：基于文化特征单元的墓葬相似度 (Jaccard)

**问题**：比较墓葬在“文化特征单元”维度上的相似性，例如反山遗址中不同墓葬的随葬品文化特征组合。

```cypher
// 第一步：为每个墓葬构造 FeatureUnit 名称集合（只保留出土文物数 >= 5 的墓葬）
MATCH (tomb:E25_Man_Made_Feature)
MATCH (tomb)<-[:P53_has_former_or_current_location]-(a:E22_Man_Made_Object)
WITH tomb, collect(DISTINCT a) AS arts
WHERE size(arts) >= 5
UNWIND arts AS art
MATCH (art)-[:HAS_FEATURE]->(fu:FeatureUnit)
WITH tomb, collect(DISTINCT fu.name) AS fuSet

// 第二步：两两墓葬做笛卡尔积，使用 APOC 计算 Jaccard（无需 GDS）
WITH collect({tomb:tomb, fuSet:fuSet}) AS rows
UNWIND rows AS r1
UNWIND rows AS r2
WITH r1, r2
WHERE id(r1.tomb) < id(r2.tomb)
WITH r1.tomb AS tombA, r2.tomb AS tombB,
     apoc.coll.toSet(r1.fuSet) AS setA,
     apoc.coll.toSet(r2.fuSet) AS setB
WITH tombA, tombB,
     size(apoc.coll.intersection(setA, setB)) AS inter,
     size(apoc.coll.union(setA, setB))        AS uni
WHERE uni > 0
RETURN tombA.name AS Tomb_A,
       tombB.name AS Tomb_B,
       toFloat(inter) / uni AS JaccardScore
ORDER BY JaccardScore DESC
LIMIT 20;
```

### 3.2 场景 B：查找与“反山 M12 墓”最相似的墓葬（基于器型 + 器物功能）

使用 V5 属性图，将“器型单元”“器物功能”两个特征联合作为墓葬的特征集合。

```cypher
// 1. 目标墓葬：反山遗址中的 M12
MATCH (site:E27_Site {name:'反山'})
MATCH (tomb_target:E25_Man_Made_Feature {name:'M12'})
WHERE (tomb_target)-[:P89_falls_within]->(:E27_Site {name:'反山'})

// 2. 目标墓葬的特征集合（器型单元 + 器物功能）
MATCH (tomb_target)<-[:P53_has_former_or_current_location]-(
         art_target:E22_Man_Made_Object
       )
OPTIONAL MATCH (art_target)-[:HAS_FEATURE]->(fu1:FeatureUnit {name:'器型单元'})
OPTIONAL MATCH (art_target)-[:HAS_FEATURE]->(fu2:FeatureUnit {name:'器物功能'})
WITH tomb_target,
     collect(DISTINCT fu1.name) + collect(DISTINCT fu2.name) AS target_fu_names

// 3. 其他墓葬的特征集合
MATCH (tomb_other:E25_Man_Made_Feature)
WHERE tomb_other <> tomb_target
MATCH (tomb_other)<-[:P53_has_former_or_current_location]-(
         art_other:E22_Man_Made_Object
       )
OPTIONAL MATCH (art_other)-[:HAS_FEATURE]->(fu1o:FeatureUnit {name:'器型单元'})
OPTIONAL MATCH (art_other)-[:HAS_FEATURE]->(fu2o:FeatureUnit {name:'器物功能'})
WITH tomb_target, target_fu_names,
     tomb_other,
     collect(DISTINCT fu1o.name) + collect(DISTINCT fu2o.name) AS other_fu_names

// 4. 手动计算 Jaccard（交集/并集）
WITH tomb_target.name AS TombA,
     tomb_other.name  AS TombB,
     apoc.coll.toSet(target_fu_names) AS setA,
     apoc.coll.toSet(other_fu_names)  AS setB
WITH TombA, TombB,
     size(apoc.coll.intersection(setA, setB)) AS inter,
     size(apoc.coll.union(setA, setB))        AS uni
WHERE uni > 0
RETURN TombA, TombB, toFloat(inter) / uni AS JaccardScore
ORDER BY JaccardScore DESC
LIMIT 10;
```

---

## 4. 路径分析 (Path Analysis)

### 4.1 场景 A：通过“神人兽面纹”连接遗址与玉器

**问题**：哪些遗址之间通过“神人兽面纹”这一纹饰主题产生联系？  
在 `jade_artifacts_export_20251203.csv` 中，`纹饰主题` 字段常出现 “神人兽面纹”、“神人兽面纹、鸟纹” 等复杂描述，因此查询时用 `CONTAINS`。

```cypher
// 1. 找到“纹饰单元”特征下，纹饰主题包含“神人兽面纹”的玉器
MATCH (fu_dec:FeatureUnit {name:'纹饰单元'})
MATCH (fm_theme:FeatureMetric {name:'纹饰主题'})-[:HAS_METRIC_OF]->(fu_dec)
MATCH (fm_theme)-[:HAS_VALUE]->(fv:FeatureValue)
WHERE fv.raw CONTAINS '神人兽面纹'

MATCH (jade:E22_Man_Made_Object {category:'Jade'})-[:HAS_METRIC]->(fm_theme)

// 2. 连接到遗址与墓葬
MATCH (jade)-[:P53_has_former_or_current_location]->(feat:E25_Man_Made_Feature)
MATCH (feat)-[:P89_falls_within]->(site:E27_Site)

RETURN site.name                AS SiteName,
       feat.name                AS TombName,
       count(DISTINCT jade)     AS JadeWithShenRenCount
ORDER BY SiteName, JadeWithShenRenCount DESC, TombName
LIMIT 50;
```

### 4.2 场景 B：遗址间通过“琮筒类玉器的量度信息”建立联系

使用 `FeatureMetric(name:'长度(cm)' / '高度(cm)' / '重量(g)')` 的属性值，查看不同遗址中“琮筒类 (Cong/Tube)”玉器的尺寸分布区间是否相似。

```cypher
// 以 M12:98 等实际数据为例，分析各遗址中琮筒类玉器的高度分布
MATCH (art:E22_Man_Made_Object)-[:P2_has_type]->(type:E55_Type)
WHERE type.name CONTAINS '琮筒类'

MATCH (art)-[:HAS_METRIC]->(fm:FeatureMetric {name:'高度(cm)'})
MATCH (fm)-[:HAS_VALUE]->(fv:FeatureValue)
WHERE fv.numeric IS NOT NULL

MATCH (art)-[:P53_has_former_or_current_location]->(:E25_Man_Made_Feature)-[:P89_falls_within]->(site:E27_Site)
RETURN site.name                           AS SiteName,
       percentileCont(fv.numeric, 0.25)    AS Q1_Height,
       percentileCont(fv.numeric, 0.5)     AS Median_Height,
       percentileCont(fv.numeric, 0.75)    AS Q3_Height,
       count(DISTINCT art)                 AS JadeCount
ORDER BY JadeCount DESC;
```

---

## 5. 典型组合与演化视角 (Evolution / Pattern)

### 5.1 场景 A：反山 M12 墓中玉器「器型单元 × 纹饰单元」组合

以反山墓地中最著名的 M12 墓为例，观察玉器**器型单元与纹饰单元的组合谱系**。

**(1) 组合频次表：哪些器型 × 纹饰组合最常见？（轻量版）**

```cypher
// 只选取 M12 墓中的 Jade 文物（编号以 "M12:" 开头）
MATCH (jade:E22_Man_Made_Object {category:'Jade'})
WHERE jade.name STARTS WITH 'M12:'

// 器型单元（取每件玉器的一个代表性器型单元）
OPTIONAL MATCH (jade)-[:HAS_METRIC]->(fm_shape:FeatureMetric)-[:HAS_METRIC_OF]->(:FeatureUnit {name:'器型单元'})
OPTIONAL MATCH (fm_shape)-[:HAS_VALUE]->(fv_shape:FeatureValue)

// 纹饰单元（同样取一个代表性纹饰单元）
OPTIONAL MATCH (jade)-[:HAS_METRIC]->(fm_dec:FeatureMetric)-[:HAS_METRIC_OF]->(:FeatureUnit {name:'纹饰单元'})
OPTIONAL MATCH (fm_dec)-[:HAS_VALUE]->(fv_dec:FeatureValue)

WITH jade,
     head(collect(DISTINCT fv_shape.raw)) AS ShapeUnit,
     head(collect(DISTINCT fv_dec.raw))   AS DecoUnit
WHERE ShapeUnit IS NOT NULL AND DecoUnit IS NOT NULL

RETURN ShapeUnit               AS 器型单元,
       DecoUnit                AS 纹饰单元,
       count(DISTINCT jade)    AS JadeCount
ORDER BY JadeCount DESC, ShapeUnit, DecoUnit;
```

**(2) 组合子图：在 Graph 视图中直观展示 M12 的器型–纹饰网络**

```cypher
// 反山 M12 墓中，玉器「器型单元 × 纹饰单元」的属性图结构

MATCH (jade:E22_Man_Made_Object {category:'Jade'})
WHERE jade.name STARTS WITH 'M12:'

// 器型单元
MATCH (fu_shape:FeatureUnit {name:'器型单元'})
MATCH (fm_shape:FeatureMetric)-[:HAS_METRIC_OF]->(fu_shape)
MATCH (jade)-[:HAS_METRIC]->(fm_shape)
MATCH (fm_shape)-[:HAS_VALUE]->(fv_shape:FeatureValue)

// 纹饰单元
MATCH (fu_dec:FeatureUnit {name:'纹饰单元'})
MATCH (fm_dec:FeatureMetric)-[:HAS_METRIC_OF]->(fu_dec)
MATCH (jade)-[:HAS_METRIC]->(fm_dec)
MATCH (fm_dec)-[:HAS_VALUE]->(fv_dec:FeatureValue)

WITH DISTINCT jade, fu_shape, fm_shape, fv_shape, fu_dec, fm_dec, fv_dec
MATCH path = (jade)-[:HAS_METRIC]->(fm_shape)-[:HAS_METRIC_OF]->(fu_shape),
             (fm_shape)-[:HAS_VALUE]->(fv_shape),
             (jade)-[:HAS_METRIC]->(fm_dec)-[:HAS_METRIC_OF]->(fu_dec),
             (fm_dec)-[:HAS_VALUE]->(fv_dec)
RETURN path
LIMIT 300;
```

### 5.2 场景 B：陶器功能类型在不同遗址时期的分布

`功能` 字段在 `pottery_artifacts_export_20251203.csv` 中被映射到特征单元“器物功能”，这里通过 `Site–Period–Pottery` 三层查看“炊煮 / 礼器 / 盛储”等功能在不同时期的分布。

```cypher
// 统计各时期各遗址中不同陶器功能的数量
MATCH (art:E22_Man_Made_Object {category:'Pottery'})

// 功能特征：器物功能
MATCH (fu_func:FeatureUnit {name:'器物功能'})
MATCH (art)-[:HAS_FEATURE]->(fu_func)-[:HAS_VALUE]->(fv:FeatureValue)

// 关联到遗址与时期：art -> tomb -> site -> period
MATCH (art)-[:P53_has_former_or_current_location]->(:E25_Man_Made_Feature)-[:P89_falls_within]->(site:E27_Site)
MATCH (period:E4_Period)-[:P7_took_place_at]->(site)

RETURN site.name             AS SiteName,
       period.name           AS PeriodName,
       fv.raw                AS FunctionLabel,
       count(DISTINCT art)   AS ArtifactCount
ORDER BY SiteName, PeriodName, ArtifactCount DESC, FunctionLabel;
```

---

## 6. 社区发现与组合模式 (Community Detection)

### 6.1 场景 A：基于“器物功能”的器物组合发现（纯 Cypher + APOC）

**目标**：不依赖 GDS，只用 APOC 找出经常一起出现的“功能组合”（例如同一墓葬中反复出现 “炊煮 + 礼器” 的组合）。

```cypher
// 1. 为每个墓葬收集陶器功能集合
MATCH (tomb:E25_Man_Made_Feature)
MATCH (tomb)<-[:P53_has_former_or_current_location]-
      (art:E22_Man_Made_Object {category:'Pottery'})
MATCH (fu_func:FeatureUnit {name:'器物功能'})
MATCH (art)-[:HAS_FEATURE]->(fu_func)-[:HAS_VALUE]->(fv:FeatureValue)
WITH tomb, collect(DISTINCT fv.raw) AS funcSet
WHERE size(funcSet) >= 2

// 2. 生成功能对组合，并统计出现在多少个墓葬中
WITH tomb, apoc.coll.combinations(funcSet, 2) AS combos
UNWIND combos AS pair
WITH pair, count(DISTINCT tomb) AS TombCount
RETURN pair[0] AS FunctionA,
       pair[1] AS FunctionB,
       TombCount
ORDER BY TombCount DESC, FunctionA, FunctionB
LIMIT 20;
```

这一结果可以被解释为“最典型的器物功能组合模式”，例如“炊煮 + 礼器”在多少座墓葬中共现。

---

## 7. 基础查询 (Basic QA)

### 7.1 查询具体文物的完整档案（含 V5 属性图）

以 `M12:98`（`jade_artifacts_export_20251203.csv` 中的玉琮）为例。

```cypher
MATCH (art:E22_Man_Made_Object {name:'M12:98'})

// 出土地：墓葬与遗址
OPTIONAL MATCH (art)-[:P53_has_former_or_current_location]->(feat:E25_Man_Made_Feature)
OPTIONAL MATCH (feat)-[:P89_falls_within]->(site:E27_Site)

// 材质 & 器型（V4 CIDOC）
OPTIONAL MATCH (art)-[:P45_consists_of]->(mat:E57_Material)
OPTIONAL MATCH (art)-[:P2_has_type]->(type:E55_Type)

// 生产信息（若已补全）
OPTIONAL MATCH (art)-[:P108i_was_produced_by]->(prod:E12_Production)
OPTIONAL MATCH (prod)-[:P32_used_general_technique]->(tech:E55_Type)
OPTIONAL MATCH (prod)-[:P4_has_time_span]->(ts:E52_Time_Span)-[:P10_falls_within]->(period:E4_Period)

// V5 属性图：FeatureUnit / Metric / Value
OPTIONAL MATCH (art)-[:HAS_FEATURE]->(fu:FeatureUnit)
OPTIONAL MATCH (fu)-[:HAS_VALUE]->(fv_fu:FeatureValue)
OPTIONAL MATCH (art)-[:HAS_METRIC]->(fm:FeatureMetric)-[:HAS_VALUE]->(fv_fm:FeatureValue)

RETURN art.name                         AS ArtifactCode,
       site.name                        AS SiteName,
       feat.name                        AS FeatureName,
       mat.name                         AS Material,
       type.name                        AS TypeName,
       tech.name                        AS ProductionTechnique,
       period.name                      AS PeriodName,
       collect(DISTINCT fu.name)        AS FeatureUnits,
       collect(DISTINCT fv_fu.raw)      AS FeatureUnitValues,
       collect(DISTINCT fm.name)        AS FeatureMetrics,
       collect(DISTINCT fv_fm.raw)      AS MetricValues;
```

### 7.2 按“神人兽面纹”筛选玉器并列出关键特征

```cypher
// 选择纹饰主题为“神人兽面纹”的玉器
MATCH (fu_dec:FeatureUnit {name:'纹饰单元'})
MATCH (fm_theme:FeatureMetric {name:'纹饰主题'})-[:HAS_METRIC_OF]->(fu_dec)
MATCH (fm_theme)-[:HAS_VALUE]->(fv:FeatureValue {raw:'神人兽面纹'})
MATCH (art:E22_Man_Made_Object {category:'Jade'})-[:HAS_METRIC]->(fm_theme)

// 补充器型与出土地
OPTIONAL MATCH (art)-[:P2_has_type]->(t:E55_Type)
OPTIONAL MATCH (art)-[:P53_has_former_or_current_location]->(feat:E25_Man_Made_Feature)
OPTIONAL MATCH (feat)-[:P89_falls_within]->(site:E27_Site)

RETURN art.name        AS ArtifactCode,
       site.name       AS SiteName,
       feat.name       AS FeatureName,
       t.name          AS TypeName,
       fv.raw          AS DecorationTheme
ORDER BY SiteName, ArtifactCode
LIMIT 50;
```

---

## 8. 研究示例：核心遗址与核心器物类型

### 8.1 寻找“核心遗址”（按文物数量与类型多样性）

下面的查询根据每个遗址关联的文物数量与类型多样性，选出“网络中最核心的遗址”：

```cypher
// 遗址的“文物数量 + 类型多样性”综合排序
MATCH (site:E27_Site)
OPTIONAL MATCH (site)<-[:P89_falls_within]-(:E25_Man_Made_Feature)
                 <-[:P53_has_former_or_current_location]-
                 (art:E22_Man_Made_Object)
OPTIONAL MATCH (art)-[:P2_has_type]->(type:E55_Type)

WITH site,
     count(DISTINCT art)  AS ArtifactCount,
     count(DISTINCT type) AS TypeCount
WHERE ArtifactCount > 0

RETURN site.name       AS SiteName,
       ArtifactCount   AS 文物数量,
       TypeCount       AS 器物类型数
ORDER BY ArtifactCount DESC, TypeCount DESC
LIMIT 20;
```

你可以将结果理解为：在当前 V5 图谱中，“文物最多、类型最丰富”的遗址，即为图谱中的“核心遗址”候选。

### 8.2 寻找“良渚遗址群”的核心器物类型（以玉器为例）

利用 Period–Site 关系，将 Period 名称中包含“良渚”的时期视为“良渚文化”相关时期，在其下属遗址中寻找最具代表性的玉器类型，并展示更多背景信息：

```cypher
// 良渚文化相关时期下，各玉器类型的出土概况
MATCH (period:E4_Period)
WHERE period.name CONTAINS '良渚'
MATCH (period)-[:P7_took_place_at]->(site:E27_Site)

MATCH (site)<-[:P89_falls_within]-(:E25_Man_Made_Feature)
             <-[:P53_has_former_or_current_location]-
             (art:E22_Man_Made_Object {category:'Jade'})
MATCH (art)-[:P2_has_type]->(type:E55_Type)

WITH type,
     collect(DISTINCT art)  AS arts,
     collect(DISTINCT site) AS sites
WITH type,
     size(arts)                     AS JadeCount,
     size(sites)                    AS SiteCount,
     [s IN sites | s.name][0..5]    AS ExampleSites,
     [a IN arts  | a.name][0..5]    AS ExampleArtifacts

RETURN type.name       AS JadeType,
       JadeCount       AS 玉器数量,
       SiteCount       AS 涉及遗址数,
       ExampleSites    AS 代表性遗址,
       ExampleArtifacts AS 代表性玉器编号
ORDER BY JadeCount DESC, SiteCount DESC, JadeType
LIMIT 30;
```

> 提示：  
> - 若想查看“良渚遗址群的**总体核心器物类型**”而不仅限于玉器，可去掉 `{category:'Jade'}` 过滤条件，即统计全部文物的 `P2_has_type`。  
> - 可以配合图 4.1/5.1 的纹饰与器型分析，一起讲解“良渚文化核心礼器谱系”。  

---

## 9. 器物相似度与 KNN（基于属性图的近邻搜索）

在 V5 的属性图结构下，可以把单件器物（特别是 Jade / Pottery）的一组关键属性（器型、纹饰、材质、工艺等）映射为“标签集合”，然后用 Jaccard 相似度或 KNN 思路来寻找“最相似”的器物。

### 9.1 场景 A：给定一件玉器，寻找最相似的其他玉器

以 `M12:98` 这件著名玉琮为例，将其若干文化特征单元转成标签集合，并在全体玉器中寻找 Jaccard 相似度最高的若干件：

```cypher
// 目标玉器编号
WITH 'M12:98' AS targetCode

// 1. 为目标玉器构造标签集合（器型单元 / 纹饰单元 / 工艺特征单元 / 材质单元）
MATCH (target:E22_Man_Made_Object {name:targetCode, category:'Jade'})
MATCH (target)-[:HAS_FEATURE]->(fu:FeatureUnit)
WHERE fu.name IN ['器型单元','纹饰单元','工艺特征单元','材质单元']

OPTIONAL MATCH (target)-[:HAS_METRIC]->(fm:FeatureMetric)-[:HAS_METRIC_OF]->(fu)
OPTIONAL MATCH (fm)-[:HAS_VALUE]->(fv_m:FeatureValue)
OPTIONAL MATCH (fu)-[:HAS_VALUE]->(fv_u:FeatureValue)

WITH target,
     collect(DISTINCT fu.name + ':' + coalesce(fv_m.raw, fv_u.raw)) AS targetTags

// 2. 为其他玉器构造同样的标签集合
MATCH (other:E22_Man_Made_Object {category:'Jade'})
WHERE other <> target
MATCH (other)-[:HAS_FEATURE]->(fu2:FeatureUnit)
WHERE fu2.name IN ['器型单元','纹饰单元','工艺特征单元','材质单元']

OPTIONAL MATCH (other)-[:HAS_METRIC]->(fm2:FeatureMetric)-[:HAS_METRIC_OF]->(fu2)
OPTIONAL MATCH (fm2)-[:HAS_VALUE]->(fv_m2:FeatureValue)
OPTIONAL MATCH (fu2)-[:HAS_VALUE]->(fv_u2:FeatureValue)

WITH target, targetTags, other,
     collect(DISTINCT fu2.name + ':' + coalesce(fv_m2.raw, fv_u2.raw)) AS otherTags

// 3. 计算 Jaccard 相似度（交集 / 并集）
WITH other, targetTags, otherTags,
     apoc.coll.intersection(targetTags, otherTags) AS inter,
     apoc.coll.union(targetTags, otherTags)        AS uni
WITH other, size(inter) AS interSize, size(uni) AS uniSize
WHERE uniSize > 0

RETURN other.name AS SimilarArtifact,
       interSize  AS SharedFeatureCount,
       toFloat(interSize) / uniSize AS JaccardScore
ORDER BY JaccardScore DESC, SharedFeatureCount DESC, SimilarArtifact
LIMIT 20;
```

> 说明：  
> - 上述查询不依赖 GDS，只需要 APOC（已经在前文用到）。  
> - 你可以将 `targetCode` 换成任意一件玉器或陶器编号，并调整 `WHERE fu.name IN [...]` 中的特征单元列表，以适配不同的研究问题。  
> - 若后续安装了 GDS，也可以基于相同的标签集合构建向量图，再用 `gds.nodeSimilarity` / KNN 算法进行更大规模的相似度计算。

---

## 10. 小结

1. V5 在保持 V4 CIDOC 主干结构的基础上，引入了 `FeatureUnit / FeatureMetric / FeatureValue` 与 `HAS_FEATURE / HAS_METRIC / HAS_VALUE` 等属性图结构，使得文化特征单元可以直接参与图计算。  
2. 本指南所有 Cypher 语句均可在当前 V5 图谱上直接执行，无需手动替换占位符；涉及的字段、节点标签与关系类型严格对应 `convert_to_graph_v5.py` 与 `CIDOC_FEATURE_FIELD_MAPPING_V5.md` 的实现。  
3. 在实际分析中，可根据研究问题自由组合 CIDOC 路径与属性图路径，构建更复杂的网络（例如“工艺特征 × 纹饰主题 × 时期 × 遗址”的多维分析，或如 9.1 中所示的器物相似度 / KNN 计算）。  


