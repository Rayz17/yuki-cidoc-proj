# 考古信息抽取系统架构设计说明书 (V2.5)

**版本**: 2.5 (主数据治理版)
**日期**: 2026-02-01
**状态**: 开发中
**核心技术栈**: 
- 后端: Python 3.11+, FastAPI, SQLAlchemy (Async/Sync), Coze API
- 前端: Streamlit

---

## 1. 项目结构

```
/
  src/
    api/            # FastAPI 路由 (Routes)
    assets/         # CSV 模板与参考数据
    core/           # 配置与日志
    db/             # 数据库模型与会话
    services/       # 业务逻辑
      - coze_client.py
      - orchestrator.py
      - parser_service.py
      - merger_service.py # [新增] 负责将抽取结果合并入主库
    main.py         # 应用入口点
  gui/              # 前端应用
    - app.py        # Streamlit 主程序
  prompts/          # Agent 系统提示词
  tests/            # 单元测试
  requirements.txt
  .env              # 环境变量
```

## 2. 核心流程与组件

### 2.1 编排器 (The Brain: Orchestrator)
负责 **"抽取 (Extract)"** 阶段：
1.  **结构化分析**: Agent A 提取实体树。
2.  **精准抽取**: Agent B 提取属性。
3.  **输出**: 产生 **"草稿数据 (Draft Data)"**，挂载于 `sys_tasks` 下，状态为 `PENDING_REVIEW`。

### 2.2 数据合并服务 (The Gatekeeper: Merger Service) [新增]
负责 **"入库 (Load/Merge)"** 阶段：
1.  **触发**: 用户在 GUI 上点击“确认入库”。
2.  **逻辑**: 
    -   遍历 Task 中的实体。
    -   检查 **主数据库 (Master Data)** 中是否已存在同名实体 (Key: Site + Type + Name)。
    -   **不存在**: 插入 (Insert)。
    -   **存在**: 更新 (Update) (覆盖旧值或补充空值，策略可配)。
3.  **结果**: 数据正式进入资产库，成为“总体数据库”的一部分。

### 2.3 数据库设计 (Schema Implementation)

我们采用 **"双层存储模型"**：

#### A. 抽取缓冲层 (Staging Layer)
*   **sys_tasks**: 任务记录。
*   **staging_entities**: 原始抽取实体，包含 `task_id`。
*   **staging_attributes**: 原始抽取属性。
*   *注：目前的 `entities` 和 `entity_attributes` 表作为缓冲层使用。*

#### B. 主数据层 (Master Layer) - [需要新增/明确]
*   **master_entities**: 
    -   `id`, `site_name`, `entity_type`, `name` (联合唯一索引)。
    -   不包含 `task_id`，因为它是跨任务的客观存在。
*   **master_attributes**:
    -   存储最终确认的属性值。
    -   包含 `last_updated_by_task_id` (用于追溯来源)。

### 2.4 前端管理控制台 (GUI Dashboard)
- **任务中心**: 上传文件，查看抽取进度。**新增 "预览与入库" 功能。**
- **资产库 (Master DB)**: 浏览合并后的、去重的总体数据。

---

## 3. 核心业务逻辑与数据治理

### 3.1 数据生命周期：从草稿到资产
1.  **上传与抽取**: 用户上传 `Report_A.txt`。系统生成 `Task 101`。抽取出了 `M1`, `M2`。此时这些数据只存在于 `Task 101` 的**暂存区**。主数据库是空的。
2.  **人工核对 (可选)**: 用户在 GUI 上查看 `Task 101` 的结果，发现 `M1` 的高度抽取错了，手动修正（或者觉得太烂直接删除任务）。
3.  **确认入库**: 用户点击“入库”。
    -   系统将 `M1`, `M2` 写入 **Master DB**。
4.  **增量更新**:
    -   用户上传 `Report_A_part2.txt`。系统生成 `Task 102`。抽取出了 `M1` (更多细节) 和 `M3`。
    -   点击“入库”。
    -   系统检测到 **Master DB** 里已经有 `M1` 了 -> **更新** `M1` 的属性（合并新细节）。
    -   系统检测到 `M3` 是新的 -> **新增** `M3`。
5.  **最终状态**: Master DB 里有完整的 `M1` (来源 Task 101+102), `M2` (来源 Task 101), `M3` (来源 Task 102)。

### 3.2 模版变更适应性
(同上版本，Master Attributes 表同样采用 EAV 结构以适应模版变化)

---

## 4. 部署与运行

**启动后端 (API)**:
```bash
source venv/bin/activate
python src/main.py
```

**启动前端 (GUI)**:
```bash
source venv/bin/activate
streamlit run gui/app.py
```

---

# English Version

# Archaeological Info Extraction System Architecture Design (V2.5)

**Version**: 2.5 (Master Data Governance)
**Date**: 2026-02-01
**Status**: In Development
**Core Tech Stack**:
- Backend: Python 3.11+, FastAPI, SQLAlchemy (Async/Sync), Coze API
- Frontend: Streamlit

---

## 1. Implementation Structure

```
/
  src/
    api/            # FastAPI Routes
    assets/         # CSV Templates & Reference Data
    core/           # Config & Logging
    db/             # Database Models & Session
    services/       # Business Logic
      - coze_client.py
      - orchestrator.py
      - parser_service.py
      - merger_service.py # [New] Merges extraction results into master DB
    main.py         # App Entrypoint
  gui/              # Frontend Application
    - app.py        # Streamlit Main App
  prompts/          # System Prompts for Agents
  tests/            # Unit Tests
  requirements.txt
  .env              # Environment Variables
```

## 2. Core Process & Components

### 2.1 The Brain: Orchestrator
Responsible for the **"Extract"** phase:
1.  **Structural Analysis**: Agent A extracts the entity tree.
2.  **Precision Extraction**: Agent B extracts attributes.
3.  **Output**: Generates **"Draft Data"**, attached under `sys_tasks` with status `PENDING_REVIEW`.

### 2.2 The Gatekeeper: Merger Service [New]
Responsible for the **"Load/Merge"** phase:
1.  **Trigger**: User clicks "Confirm Merge" on GUI.
2.  **Logic**:
    -   Iterate through entities in the Task.
    -   Check if entity exists in **Master Data** (Key: Site + Type + Name).
    -   **Not Exists**: Insert.
    -   **Exists**: Update (overwrite old values or fill empty ones, strategy configurable).
3.  **Result**: Data officially enters the Asset Library, becoming part of the "Master Database".

### 2.3 Schema Implementation

We use a **"Dual-Layer Storage Model"**:

#### A. Staging Layer
*   **sys_tasks**: Task records.
*   **staging_entities**: Raw extracted entities, includes `task_id`.
*   **staging_attributes**: Raw extracted attributes.
*   *Note: current `entities` and `entity_attributes` tables serve as the staging layer.*

#### B. Master Layer - [New/Explicit]
*   **master_entities**:
    -   `id`, `site_name`, `entity_type`, `name` (Unique Constraint).
    -   Does not contain `task_id` as it exists objectively across tasks.
*   **master_attributes**:
    -   Stores finalized attribute values.
    -   Includes `last_updated_by_task_id` (for lineage).

### 2.4 GUI Dashboard
- **Task Center**: File upload, view extraction progress. **Added "Preview & Merge" function.**
- **Asset Library (Master DB)**: Browse merged, deduplicated master data.

---

## 3. Core Logic & Governance

### 3.1 Data Lifecycle: From Draft to Asset
1.  **Upload & Extract**: User uploads `Report_A.txt`. System generates `Task 101`. Extracts `M1`, `M2`. Data exists only in `Task 101` **Staging Area**. Master DB is empty.
2.  **Manual Review (Optional)**: User checks `Task 101` in GUI, finds `M1` height extracted incorrectly, fixes manually (or deletes task if too poor).
3.  **Confirm Merge**: User clicks "Merge".
    -   System writes `M1`, `M2` into **Master DB**.
4.  **Incremental Update**:
    -   User uploads `Report_A_part2.txt`. System generates `Task 102`. Extracts `M1` (more details) and `M3`.
    -   Clicks "Merge".
    -   System detects `M1` exists in **Master DB** -> **Updates** `M1` attributes (merges new details).
    -   System detects `M3` is new -> **Inserts** `M3`.
5.  **Final State**: Master DB has complete `M1` (from Task 101+102), `M2` (from Task 101), `M3` (from Task 102).

### 3.2 Template Flexibility
(Same as previous version, Master Attributes table uses EAV structure to adapt to template changes)

---

## 4. Deployment

**Start Backend (API)**:
```bash
source venv/bin/activate
python src/main.py
```

**Start Frontend (GUI)**:
```bash
source venv/bin/activate
streamlit run gui/app.py
```
