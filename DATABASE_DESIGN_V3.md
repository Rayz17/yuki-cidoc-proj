# 考古文物数据库设计方案 V3.1 (CIDOC增强版)

## 1. 核心改进：双层存储与知识图谱支持

为了满足“数据无损覆盖”和“CIDOC-CRM 知识图谱化”的需求，V3.1 版本采用了 **“结构化字段 + 原始数据(JSON) + 语义数据(JSON)”** 的混合存储模式。

### 1.1 存储策略

1.  **结构化字段 (Relational Columns)**
    *   **用途**：快速查询、筛选、统计、排序。
    *   **内容**：通用的核心指标，如 `artifact_code`, `height`, `site_id`。
    *   **关系**：N 个结构化字段 可能对应 1 个抽取属性（如 `dimensions` 拆分为长宽高）。

2.  **原始数据 (Raw Attributes - JSON)**
    *   **用途**：数据溯源、完整性保证、GUI 详情展示。
    *   **内容**：**原封不动**存储 LLM 抽取的结果。Key 为 Excel 模板中的“抽取属性”。
    *   **覆盖率**：**100%**。模板里有什么，这里就存什么。

3.  **CIDOC 语义数据 (CIDOC Attributes - JSON)**
    *   **用途**：知识图谱构建、语义关联。
    *   **内容**：结合模板中的 CIDOC 定义，存储结构化的三元组元数据。
    *   **结构示例**：
      ```json
      {
        "陶土种类": {
          "value": "夹砂红陶",
          "entity_type": "E22_Man-Made_Object",
          "property": "P45_consists_of",
          "target_class": "E57_Material"
        }
      }
      ```

---

## 2. 数据库表结构变更 (Schema Changes)

所有四个主体表 (`sites`, `periods`, `pottery_artifacts`, `jade_artifacts`) 均增加以下两个核心字段：

```sql
-- 原始抽取数据（100%覆盖模板属性）
raw_attributes TEXT,  -- JSON format

-- CIDOC语义数据（用于KG构建）
cidoc_attributes TEXT -- JSON format
```

### 2.1 更新后的陶器表 (pottery_artifacts)

```sql
CREATE TABLE pottery_artifacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    site_id INTEGER,  -- 允许为空
    
    -- 核心识别信息
    artifact_code TEXT,     -- 对应模板：人工物品编号
    artifact_type TEXT,     -- 对应模板：文物类型
    
    -- 结构化查询字段 (精选常用字段)
    subtype TEXT,           -- 对应：基本器型
    clay_type TEXT,         -- 对应：陶土种类
    color TEXT,             -- 对应：颜色/色泽
    height REAL,            -- 从“量度信息”中解析
    diameter REAL,          -- 从“量度信息”中解析
    
    -- === 核心改进 ===
    -- 1. 原始数据层：存储 { "陶土种类": "夹砂陶", "纹饰类型": "绳纹", ... }
    raw_attributes TEXT,
    
    -- 2. 语义层：存储 CIDOC 映射信息
    cidoc_attributes TEXT,
    
    -- 元数据
    source_text_blocks TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 3. 映射与转换逻辑

### 3.1 抽取属性 -> 库表字段 (写入时)

*   **Step 1: 抽取**
    LLM 返回：`{ "陶土种类": "夹砂陶", "人工物品编号": "M1:1" }`
*   **Step 2: 存入 Raw**
    `raw_attributes` = `json.dumps({...})`
*   **Step 3: 存入 CIDOC**
    读取模板元数据，构建：
    `cidoc_attributes` = `json.dumps({ "陶土种类": { "value": "夹砂陶", "property": "P45..." } })`
*   **Step 4: 映射核心字段**
    `clay_type` = "夹砂陶"
    `artifact_code` = "M1:1"

### 3.2 库表字段 -> 抽取属性 (读取/展示时)

*   **方案 A (推荐)**：直接读取 `raw_attributes` 并解析 JSON。这是最准确的还原方式。
*   **方案 B**：如果需要从 `clay_type` 还原，仅用于那些没有 raw_data 的遗留数据。

---

## 4. 知识图谱化 (Future Work)

基于 `cidoc_attributes` 列，可以轻松编写脚本导出 RDF/Turtle 文件或导入 Neo4j：

```python
# 伪代码：导出为三元组
for artifact in db.query("SELECT id, cidoc_attributes FROM pottery_artifacts"):
    data = json.loads(artifact['cidoc_attributes'])
    subject_uri = f"http://kg.example.org/artifact/{artifact['id']}"
    
    for attr, info in data.items():
        predicate = info['property']  # e.g., P45_consists_of
        object_value = info['value']
        
        graph.add((subject_uri, predicate, object_value))
```
