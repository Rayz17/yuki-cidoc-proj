# CIDOC-CRM 知识图谱分析与计算指南 (V4.0)

本指南基于 **V4 语义增强版图谱结构**，提供针对五大核心计算场景的 **Cypher 查询模版**与**实战用例**。

**前提条件：**
1.  已完成 V4 数据导入。
2.  已安装 **Neo4j Graph Data Science (GDS)** 插件（部分高级算法需要）。

---

## 1. 节点中心度分析 (Centrality)

**业务场景**：
*   识别考古网络中最重要的“核心遗迹单位”（如高等级墓葬）。
*   找出跨遗址、跨时期最通用的“核心器型”。

### 场景 A：寻找“影响力”最大的器物类型
逻辑：如果某种器型（如玉琮）连接了大量高等级墓葬和遗址，它的中心度就高。

**Cypher 模版：**
```cypher
// 使用 PageRank 算法计算类型节点的重要性
CALL gds.pageRank.stream({
  nodeProjection: ['E55_Type', 'E22_Man_Made_Object'],
  relationshipProjection: 'P2_has_type'
})
YIELD nodeId, score
WITH gds.util.asNode(nodeId) AS node, score
WHERE 'E55_Type' IN labels(node)
RETURN node.name AS TypeName, score
ORDER BY score DESC LIMIT 10;
```

**实战用例：统计各遗址出土数量最多的核心器型**
```cypher
MATCH (site:E27_Site)<-[:P89_falls_within]-(:E53_Place)<-[:P89_falls_within]-(feat:E25_Man_Made_Feature)
MATCH (feat)<-[:P53_has_former_or_current_location]-(art:E22_Man_Made_Object)
MATCH (art)-[:P2_has_type]->(type:E55_Type)
RETURN site.name, type.name, count(art) AS frequency
ORDER BY frequency DESC
LIMIT 20;
```

---

## 2. 相似度计算 (Similarity)

**业务场景**：
*   **墓葬聚类**：比较不同墓葬随葬品组合的相似性，推断墓主等级或族属关系。
*   **遗址对比**：量化两个遗址在文化面貌上的重合度。

### 场景 A：基于随葬品组合计算墓葬相似度 (Jaccard)
逻辑：两个墓葬出土的“器型”重合度越高，越相似。

**Cypher 模版：**
```cypher
MATCH (tomb:E25_Man_Made_Feature)
// 只有出土文物超过 5 件的墓葬才纳入计算
WHERE size((tomb)<-[:P53_has_former_or_current_location]-()) > 5
MATCH (tomb)<-[:P53_has_former_or_current_location]-(art:E22_Man_Made_Object)-[:P2_has_type]->(type:E55_Type)
WITH {item:id(tomb), categories: collect(id(type))} AS userData
WITH collect(userData) AS data
CALL gds.alpha.similarity.jaccard.stream({
  data: data,
  topK: 3 // 只返回最相似的前3个
})
YIELD item1, item2, similarity
RETURN gds.util.asNode(item1).name AS Tomb_A, 
       gds.util.asNode(item2).name AS Tomb_B, 
       similarity
ORDER BY similarity DESC;
```

**实战用例：查找与 "M12" 号墓最相似的其他墓葬**
```cypher
// 1. 找到目标墓葬 M12 的所有器型集合
MATCH (target:E25_Man_Made_Feature {name: 'M12'})<-[:P53_has_former_or_current_location]-(art)-[:P2_has_type]->(type)
WITH target, collect(distinct type.name) as target_types

// 2. 遍历其他墓葬
MATCH (other:E25_Man_Made_Feature) WHERE other <> target
MATCH (other)<-[:P53_has_former_or_current_location]-(art2)-[:P2_has_type]->(type2)
WITH target, target_types, other, collect(distinct type2.name) as other_types

// 3. 手动计算 Jaccard 系数 (交集/并集)
WITH target.name as TombA, other.name as TombB,
     size(apoc.coll.intersection(target_types, other_types)) as intersection,
     size(apoc.coll.union(target_types, other_types)) as union_count
RETURN TombA, TombB, toFloat(intersection)/union_count as JaccardScore
ORDER BY JaccardScore DESC
LIMIT 10;
```

---

## 3. 路径分析 (Path Analysis)

**业务场景**：
*   **文化传播**：追踪某种特定工艺（如微雕）或材质（如透闪石）是如何连接不同遗址的。
*   **关联发现**：发现两个看似无关的遗址之间隐藏的联系。

### 场景 A：遗址间的最短文化路径
逻辑：通过共享的“概念”（类型、材质、工艺）来连接遗址。

**Cypher 模版：**
```cypher
MATCH (s1:E27_Site {name: '反山遗址'}), (s2:E27_Site {name: '瑶山遗址'})
MATCH p = shortestPath((s1)-[*]-(s2))
RETURN p;
```

**实战用例：查询“反山”与“瑶山”通过哪些“玉器类型”产生关联**
```cypher
MATCH (s1:E27_Site {name: '反山'}), (s2:E27_Site {name: '瑶山'})
MATCH (s1)<-[:P89_falls_within]-(:E25_Man_Made_Feature)<-[:P53_has_former_or_current_location]-(art1:E22_Man_Made_Object)
MATCH (s2)<-[:P89_falls_within]-(:E25_Man_Made_Feature)<-[:P53_has_former_or_current_location]-(art2:E22_Man_Made_Object)
// 核心关联点：共有类型
MATCH (art1)-[:P2_has_type]->(commonType:E55_Type)<-[:P2_has_type]-(art2)
RETURN s1.name, s2.name, commonType.name, count(art1) as CountA, count(art2) as CountB
ORDER BY CountA + CountB DESC;
```

---

## 4. 系统发生树 (Phylogenetic/Evolutionary Tree)

**业务场景**：
*   推断器物形态的演变序列（例如：从 A型鼎 -> B型鼎）。
*   由于图谱中没有直接的“演变自”关系，我们需要结合 **时间 (Period)** 和 **类型 (Type)** 进行推断。

### 场景 A：基于时间序列的器型演变推断
逻辑：列出某一大类（如“鼎”）下的所有子类型，按其出现的最早时间排序，生成演变序列假设。

**Cypher 模版：**
```cypher
MATCH (art:E22_Man_Made_Object)-[:P2_has_type]->(type:E55_Type)
WHERE type.name CONTAINS '鼎' // 筛选大类
// 关联时间：Artifact -> Production -> Period
MATCH (art)-[:P108i_was_produced_by]->(:E12_Production)-[:P4_has_time_span]->(p:E4_Period)
RETURN type.name, min(p.start_date) as FirstAppearance, collect(distinct p.name) as Periods
ORDER BY FirstAppearance
```

**实战用例：玉器工艺的时间演变分析**
```cypher
// 分析不同玉器工艺在各个时期的流行程度
MATCH (prod:E12_Production)-[:P32_used_general_technique]->(tech:E55_Type)
MATCH (prod)-[:P4_has_time_span]->(period:E4_Period)
RETURN period.name, tech.name, count(prod) as usage_count
ORDER BY period.start_date, usage_count DESC;
```

---

## 5. 社区发现 (Community Detection)

**业务场景**：
*   **器物组合发现**：不预设分类，让算法自动发现经常一起出现的“器物套装”（如鼎簋组合）。
*   **文化圈层划分**：根据出土物特征，将遗址自动划分为不同的文化圈。

### 场景 A：基于共现关系的器物组合发现 (Louvain)
逻辑：如果两个类型经常在同一个墓葬中出现，它们就属于同一个“社区”。

**第一步：构建共现图 (Graph Projection)**
*(需要在 GDS 中执行)*
```cypher
// 1. 创建内存图：类型与类型之间的共现关系
CALL gds.graph.project.cypher(
  'co_occurrence_graph',
  'MATCH (n:E55_Type) RETURN id(n) as id',
  'MATCH (t1:E55_Type)<-[:P2_has_type]-(a1)-[:P53_has_former_or_current_location]->(feat)<-[:P53_has_former_or_current_location]-(a2)-[:P2_has_type]->(t2:E55_Type)
   WHERE id(t1) < id(t2)
   RETURN id(t1) as source, id(t2) as target, count(*) as weight'
)
```

**第二步：运行 Louvain 算法**
```cypher
CALL gds.louvain.stream('co_occurrence_graph')
YIELD nodeId, communityId
WITH gds.util.asNode(nodeId) as type, communityId
RETURN communityId, collect(type.name) as ArtifactPackage
ORDER BY size(ArtifactPackage) DESC;
```
*结果解读：每一个 `ArtifactPackage` 就是一个算法自动发现的“器物组合”（例如：社区1可能是 [玉琮, 玉钺, 玉璧]，代表高等级礼器组合）。*

---

## 6. 基础查询 (Basic QA)

**Q: 查询某个遗址（如反山）的所有层级结构？**
```cypher
MATCH (s:E27_Site {name: '反山'})
OPTIONAL MATCH (s)<-[:P89_falls_within]-(p:E53_Place)
OPTIONAL MATCH (p)<-[:P89_falls_within]-(f:E25_Man_Made_Feature)
RETURN s.name, p.name, collect(f.name) as features;
```

**Q: 查询特定文物的完整档案（材质、尺寸、工艺、出土地、年代）？**
```cypher
MATCH (art:E22_Man_Made_Object {name: 'M12:98'})
// 出土地
OPTIONAL MATCH (art)-[:P53_has_former_or_current_location]->(feat)
// 材质 & 类型
OPTIONAL MATCH (art)-[:P45_consists_of]->(mat:E57_Material)
OPTIONAL MATCH (art)-[:P2_has_type]->(type:E55_Type)
// 生产信息 (工艺 & 年代)
OPTIONAL MATCH (art)-[:P108i_was_produced_by]->(prod:E12_Production)
OPTIONAL MATCH (prod)-[:P32_used_general_technique]->(tech:E55_Type)
OPTIONAL MATCH (prod)-[:P4_has_time_span]->(period:E4_Period)
RETURN art.name, feat.name, mat.name, type.name, tech.name, period.name;
```

