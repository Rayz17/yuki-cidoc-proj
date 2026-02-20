# 系统重构计划：Schema 层级化与深度抽取 (V3.0) - 修订版

## 1. 核心目标
解决当前系统因“扁平化解析”导致的 Schema 信息丢失问题，实现对 CSV 模板中**层级结构**和**属性族**的完整支持。同时，**重构数据库设计**以匹配层级结构，并强制要求**每个属性值都必须包含原文引用 (Quote)** 作为证据。

## 2. 改造模块与方案

### 2.1 数据库重构 (`src/db/models.py`)
*   **原则**：放弃兼容性，优先保证数据结构的完整性和可追溯性。
*   **变更**：
    *   **EntityAttribute 表**：
        *   新增 `quote` 字段 (Text)：存储该属性值的原文依据。
        *   `attribute_code` 字段含义变更：支持**点分路径**（Dot Notation）以表示层级。
            *   旧：`ProductionDate`
            *   新：`ProductionDate.C2.cultural_period`
    *   **MasterAttribute 表**：同步增加 `quote` 字段。
    *   **数据迁移**：由于表结构变更，建议**清空旧数据**（Drop Tables）重新初始化。

### 2.2 解析器重构 (`src/services/parser_service.py`)
*   **逻辑升级**：
    *   **层级识别**：解析器将识别 `CAU ID`（根节点）、`一级指标`（子节点）、`二级指标`（孙节点）以及**三级指标（重孙节点）**。
    *   **代码提取**：自动从“C2：相对年代”或“P1F1：敞收程度”这样的文本中提取出代码。
    *   **输出结构**：生成一颗完整的 Schema 树（Tree Structure），支持任意深度的嵌套（目前最大深度为 3），供 Agent B 理解字段间的嵌套关系。

### 2.3 Agent B 提示词升级 (`prompts/agent_b_extraction_v3.md`)
*   **输出格式变更**：
    *   不再返回扁平的 Key-Value。
    *   **必须返回嵌套 JSON 对象**，且每个叶子节点（Leaf Node）必须包含 `value` 和 `quote`。
    *   示例：
        ```json
        {
          "ProductionDate": {
            "type": "C2",
            "C2": {
              "cultural_period": { 
                "value": "龙山文化晚期", 
                "quote": "遗址上层发现大量龙山文化晚期陶片" 
              }
            }
          }
        }
        ```

### 2.4 业务逻辑适配 (`src/services/orchestrator.py`)
*   **扁平化存储 (Flattening)**：
    *   收到 Agent B 的嵌套 JSON 后，Orchestrator 负责将其**扁平化**为数据库行。
    *   例如将上面的 JSON 转换为：
        1.  Code: `ProductionDate.type`, Value: `C2`, Quote: `...`
        2.  Code: `ProductionDate.C2.cultural_period`, Value: `龙山文化晚期`, Quote: `...`
    *   这样既保留了层级语义（通过 Code 路径），又利用了关系型数据库的查询能力。

### 2.5 GUI 适配 (`gui/app.py`)
*   **展示优化**：
    *   **层级展示**：解析 `attribute_code` 中的点（.），在 UI 上以**分组/树形**方式展示属性。
    *   **证据展示**：在每个属性值旁边显示 `📜 Quote`，鼠标悬停或点击可查看原文依据。
    *   **字典映射**：利用 Schema 树，将 `C2` 等代码自动转义为中文名称。

## 3. 执行步骤

1.  **数据库重置**：修改 `models.py`，删除旧 `.db` 文件（或 Drop Tables）。
2.  **解析器开发**：重写 `SchemaParser`，支持层级树构建。
3.  **Prompt V3 编写**：定义新的嵌套 JSON + Quote 输出格式。
4.  **Orchestrator 升级**：实现 JSON -> Flattened Rows 的转换逻辑。
5.  **GUI 升级**：适配新的数据结构和 Quote 展示。
6.  **验证**：使用测试用例验证层级数据的完整性和 Quote 的准确性。

请确认此修订后的计划？
