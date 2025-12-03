# CIDOC-CRM 知识图谱构建方案与实施指南

## 1. 方案概述

本方案旨在基于 **CIDOC-CRM (ISO 21127)** 国际文化遗产数据标准，将考古发掘报告中的结构化数据（CSV）转换为语义丰富的**知识图谱（Knowledge Graph）**。

与简单的属性图（Property Graph）不同，本方案采用**元数据驱动（Metadata-Driven）**的构建策略，严格遵循 `cidoc-kg-def3.csv` 中定义的本体结构。也就是说：**所有字段如何映射到图谱结构，完全由 CSV 定义表决定**，代码只是一个“执行者”，不会再硬编码任何业务字段名称。这保证了图谱的**互通性**和**可验证性**。

### 核心价值
*   **学术合规性**：符合数字人文与文化遗产领域的国际标准。
*   **语义无损**：保留了“实体”与“概念”、“事件”与“结果”之间的微妙语义差别。
*   **复杂推理**：支持跨遗址、跨时期的深层语义查询（如：“查找所有使用特定工艺且产出于特定时期的器物”）。

---

## 2. 图谱模型设计

### 2.1 数据映射逻辑

我们将扁平的 CSV 数据表转化为立体的网状结构。**所有映射规则完全由 `cidoc-kg-def3.csv` 定义**。

**核心映射模式：**

1.  **直接属性模式 (Direct Property)**
    *   *CSV*: `陶器.陶土种类 = "泥质红陶"`
    *   *CIDOC*: `E22_Man-Made_Object` --[`P45_consists_of`]--> `E57_Material` --[`P2_has_type`]--> `E55_Type("泥质红陶")`
    *   *解释*：文物由某种材质构成，该材质属于“泥质红陶”这一类型。

2.  **事件中介模式 (Event-Based Property)**
    *   *CSV*: `陶器.成型工艺 = "轮制"`
    *   *CIDOC*: `E22_Man-Made_Object` --[`P108_was_produced_by`]--> `E12_Production` --[`P32_used_general_technique`]--> `E55_Type("轮制")`
    *   *解释*：文物的属性（如工艺、年代、制作者）往往不是直接挂在文物上，而是通过一个**“生产事件”**（Production Event）来关联。这使得我们可以在同一个事件节点上聚合时间、地点和工艺信息。

3.  **量度模式 (Dimension)**
    *   *CSV*: `陶器.高度 = 15.5`
    *   *CIDOC*: `E22_Man-Made_Object` --[`P43_has_dimension`]--> `E54_Dimension` (value: 15.5, unit: cm)
    *   *解释*：将尺寸数值化为独立对象，便于后续的数值计算和单位换算。

### 2.2 节点类型 (Node Labels)

| 标签 (Label) | CIDOC 类 | 描述 | 示例 |
| :--- | :--- | :--- | :--- |
| **E22_ManMade_Object** | E22 | 人造物品（核心实体） | 陶罐 M1:23, 玉琮 M12:98 |
| **E27_Site** | E27 | 遗址 | 良渚古城, 反山遗址 |
| **E25_ManMade_Feature** | E25 | 人工遗迹/结构 | M12号墓, H3灰坑 |
| **E4_Period** | E4 | 时期 | 良渚文化晚期 |
| **E12_Production** | E12 | 生产事件 | (虚拟节点，代表制造过程) |
| **E57_Material** | E57 | 材质 | (虚拟节点，代表某件器物的材质部分) |
| **E55_Type** | E55 | 类型/概念 | 泥质红陶, 鼎, 兽面纹, 轮制 |
| **E54_Dimension** | E54 | 量度 | (虚拟节点，存储数值) |

---

## 3. 实际案例解析（从 CSV 到 CIDOC 路径）

假设我们有一条陶器数据：
*   **编号**: `P001`
*   **器型**: `鼎`
*   **陶土**: `夹砂红陶`
*   **成型**: `轮制`
*   **高度(cm)**: `15.5`

在 Neo4j 中生成的子图结构（简化）如下：

```mermaid
graph LR
    Art(P001: E22_ManMade_Object)
    
    %% 器型分类
    Type1(鼎: E55_Type)
    Art -- P2_has_type --> Type1
    
    %% 材质路径
    Mat(Material_Node: E57_Material)
    Type2(夹砂红陶: E55_Type)
    Art -- P45_consists_of --> Mat
    Mat -- P2_has_type --> Type2
    
    %% 生产工艺路径
    Prod(Production_Event: E12_Production)
    Type3(轮制: E55_Type)
    Art -- P108_was_produced_by --> Prod
    Prod -- P32_used_general_technique --> Type3
    
    %% 尺寸路径
    DimH(Height: E54_Dimension)
    Art -- P43_has_dimension --> DimH
    DimH -- P90_has_value -->|"15.5"| Val( )
    DimH -- P91_has_unit -->|"cm"| Unit( )
```

> 说明：上图中的 `Val` 与 `Unit` 在实际实现中可以直接作为 `E54_Dimension` 节点的属性存储（例如 `value=15.5, unit="cm"`），也可以进一步拆成节点。本方案采用**属性方式**以简化实现。

---

## 4. 实施步骤

### 步骤 1: 准备数据（输入）
确保以下文件位于 `for-neo4j/` 目录下：
1.  `cidoc-kg-def3.csv` (定义表)
2.  `pottery_artifacts_export_20251203.csv`
3.  `jade_artifacts_export_20251203.csv`
4.  `sites_export_20251203.csv`
5.  `site_structures_export_20251203.csv`
6.  `periods_export_20251203.csv`

### 步骤 2: 安装依赖并激活虚拟环境

项目已经在 `requirements.txt` 中声明了 `pandas` 依赖，用于处理 CSV。

在项目根目录执行（仅需一次）：

```bash
cd /Users/rayz/Downloads/yuki-cidoc-proj
source venv/bin/activate      # 使用已有虚拟环境
pip install -r requirements.txt
```

### 步骤 3: 运行转换脚本
运行 Python 脚本 `for-neo4j/convert_cidoc_strict.py`。该脚本会：
1.  解析 CIDOC 定义表。
2.  读取所有业务数据。
3.  根据定义生成对应的 CIDOC 路径（包括中间类 E12/E57/E54/E55 等）。
4.  在 `neo4j_cidoc_import/` 目录下生成一系列 **节点 CSV**（按 CIDOC 类拆分）和一份 **关系 CSV**。

命令示例：

```bash
cd /Users/rayz/Downloads/yuki-cidoc-proj
source venv/bin/activate
python for-neo4j/convert_cidoc_strict.py
```

脚本结束后，你可以在 `neo4j_cidoc_import/` 目录看到类似结构：

```text
neo4j_cidoc_import/
  nodes_E22_ManMade_Object.csv
  nodes_E27_Site.csv
  nodes_E25_ManMade_Feature.csv
  nodes_E4_Period.csv
  nodes_E12_Production.csv
  nodes_E57_Material.csv
  nodes_E55_Type.csv
  nodes_E54_Dimension.csv
  relationships.csv
```

每个节点文件都包含：

```text
id:ID,:LABEL,name,...  # 其中 :LABEL 为 CIDOC 类（例如 E22_ManMade_Object）
```

`relationships.csv` 包含：

```text
:START_ID,:END_ID,:TYPE
Artifact_xxx,Material_yyy,P45_consists_of
...
```

### 步骤 4: 导入 Neo4j（使用 neo4j-admin import）

> 建议：用于正式部署或大规模数据时使用 `neo4j-admin import`，用于小规模调试可以使用 `LOAD CSV`。

1. 将 `neo4j_cidoc_import/` 拷贝或链接到 Neo4j 的 `import/` 目录。
2. 停止数据库服务（例如 Neo4j Desktop 中 Stop 数据库）。
3. 在 Neo4j 安装目录执行导入命令（根据实际文件名调整）：

```bash
./bin/neo4j-admin database import full \
  --nodes=import/nodes_E22_ManMade_Object.csv \
  --nodes=import/nodes_E27_Site.csv \
  --nodes=import/nodes_E25_ManMade_Feature.csv \
  --nodes=import/nodes_E4_Period.csv \
  --nodes=import/nodes_E12_Production.csv \
  --nodes=import/nodes_E57_Material.csv \
  --nodes=import/nodes_E55_Type.csv \
  --nodes=import/nodes_E54_Dimension.csv \
  --relationships=import/relationships.csv \
  --overwrite-destination neo4j
```

4. 启动数据库，打开 Neo4j Browser（通常是 `http://localhost:7474`）。

### 步骤 5: （可选）使用 LOAD CSV 增量导入 / 调试

如果你只想导入一小部分数据进行调试，可以直接使用 `LOAD CSV`：

```cypher
// 以 E27_Site 为例
LOAD CSV WITH HEADERS FROM 'file:///nodes_E27_Site.csv' AS row
MERGE (s:E27_Site {id: row.`id:ID`})
SET s.name = row.name,
    s.type = row.type,
    s.location = row.location;

// 导入关系
LOAD CSV WITH HEADERS FROM 'file:///relationships.csv' AS row
MATCH (a {id: row.`:START_ID`})
MATCH (b {id: row.`:END_ID`})
MERGE (a)-[r:REL {type: row.`:TYPE`}]->(b);
```

实际项目中，可以根据 `:TYPE` 动态分发到不同的关系类型，这里仅作为调试示例。

---

## 5. Cypher 查询用例

### 用例 1: 基础检索（按器型 + 遗址）
**查询**: 查找所有出土于“反山遗址”的“玉琮”。
```cypher
MATCH (site:E27_Site {name: "反山"})
MATCH (art:E22_ManMade_Object)
MATCH (art)-[:P53_has_former_or_current_location]->(:E25_ManMade_Feature)-[:P53_has_former_or_current_location]->(site)
MATCH (art)-[:P2_has_type]->(type:E55_Type {name: "玉琮"})
RETURN art.code, art.description
```

### 用例 2: 工艺分析 (多跳路径)
**查询**: 查找使用了“轮制”工艺且材质为“泥质黑陶”的器物。
```cypher
MATCH (art:E22_ManMade_Object)
// 路径 A: 生产 -> 工艺
MATCH (art)-[:P108_was_produced_by]->(prod:E12_Production)-[:P32_used_general_technique]->(tech:E55_Type {name: "轮制"})
// 路径 B: 材质 -> 类型
MATCH (art)-[:P45_consists_of]->(mat:E57_Material)-[:P2_has_type]->(mat_type:E55_Type {name: "泥质黑陶"})
RETURN art.code
```

### 用例 3: 尺寸统计
**查询**: 统计“良渚文化”时期所有“鼎”的平均高度。
```cypher
MATCH (p:E4_Period {name: "良渚文化"})
MATCH (art:E22_ManMade_Object)-[:P2_has_type]->(:E55_Type {name: "鼎"})
// 假设文物关联到了时期 (通过出土层位或直接关联)
MATCH (art)-[:P108_was_produced_by]->(prod:E12_Production)-[:P4_has_time_span]->(p)
MATCH (art)-[:P43_has_dimension]->(dim:E54_Dimension {metric: "高度"})
RETURN avg(toFloat(dim.value)) as avg_height
```

### 用例 4: 语义拼接 —— “材质 + 工艺 + 时期 + 遗址”

**问题**：查找“在反山遗址、良渚文化时期、使用轮制工艺制作的泥质红陶鼎”。

```cypher
// 反山遗址 & 良渚文化时期
MATCH (site:E27_Site {name: "反山"})
MATCH (period:E4_Period {name: "良渚文化"})

// 文物 & 器型 = 鼎
MATCH (art:E22_ManMade_Object)-[:P2_has_type]->(:E55_Type {name: "鼎"})

// 出土地点在反山（通过结构单元）
MATCH (art)-[:P53_has_former_or_current_location]->(:E25_ManMade_Feature)-[:P53_has_former_or_current_location]->(site)

// 生产事件落在该时期
MATCH (art)-[:P108_was_produced_by]->(prod:E12_Production)
MATCH (prod)-[:P4_has_time_span]->(period)

// 工艺 = 轮制
MATCH (prod)-[:P32_used_general_technique]->(:E55_Type {name: "轮制"})

// 材质 = 泥质红陶
MATCH (art)-[:P45_consists_of]->(:E57_Material)-[:P2_has_type]->(:E55_Type {name: "泥质红陶"})

RETURN art.code AS artifact_code
```

---

## 6. 实现细节总览（给开发者）

### 6.1 `convert_cidoc_strict.py` 的核心逻辑

- **输入**：`cidoc-kg-def3.csv` + 多个业务 CSV。
- **步骤**：
  1. **解析定义表**：为每一行生成一条“映射规则”：  
     - 关键字段：`文物类型` + `抽取属性：文化特征单元` 组成键  
     - 值包含：`Domain (E22/E27/...)`，`Property1 (Pxx)`，`中间类 (E12/E57)`，`子属性 (Pyy)`，`目标类 (Range Class)`。
  2. **遍历业务数据**：对每一行、每一列，根据 `(文物类型, 列名)` 查找规则，如果存在：
     - 如果没有中间类：生成一条 `Domain -> Range` 的 CIDOC 边；
     - 如果有中间类：生成 `Domain -> 中间类 -> Range` 的两跳路径，并为中间类和范围类生成节点。
  3. **基础拓扑补全**：为 Site / Structure / Period 建立：
     - `E25_ManMade_Feature` -> `E27_Site` 的 P53 关系；
     - `E25_ManMade_Feature` -> `E25_ManMade_Feature` 的 P46i（结构层级）；
     - `E4_Period` -> `E27_Site` 的 P7 关系；
  4. **导出 CSV**：每个 CIDOC 类一个节点文件，所有关系合并为一份关系文件。

### 6.2 与简单“属性图方案”的区别

- 不再直接写死 `Artifact-[:CONSISTS_OF]->Material` 等关系，而是**完全以 `cidoc-kg-def3.csv` 为真**；
- 通过中间类（E12/E57/E54）显式表达“事件”、“材质部分”、“量度”等学界认可的抽象；
- 使得本项目的图谱可以与其他 CIDOC-CRM 图谱（博物馆数据库、考古项目）进行对接与联邦查询。

如果后续你更新了 `cidoc-kg-def3.csv`（例如新增“石器”、“建筑单元”等），只需重新运行脚本即可，整个图谱结构会自动随之演化，无需改代码。


