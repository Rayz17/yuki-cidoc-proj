# 考古信息抽取系统实施手册 (V3.1)

**版本**: 3.1 (增强的 GUI 与数据治理)
**日期**: 2026-02-01
**适用场景**: Cursor 开发 -> Windows Server 2019 部署
**核心架构**: Streamlit (GUI) + FastAPI (Backend) + Coze Agents (LLM)

---

## 1. 项目目录结构规范

基于 V2.5 架构，采用前后端分离但同构部署的模式。

```text
/project_root
  /src                        <-- [后端源码]
    /api                      <-- FastAPI 接口
    /assets                   <-- [资产] 存放生产环境模版 (CSV)
      template_site.csv       <-- 遗址模版
      template_pottery.csv    <-- 陶器模版
      ...
    /core                     <-- 配置与日志
    /db                       <-- 数据库模型 (Models & Init)
    /services                 <-- 核心业务逻辑
      orchestrator.py         <-- 编排器 (Admin-Clerk 模式)
      merger_service.py       <-- [新增] 数据入库合并服务
      parser_service.py       <-- CSV 模版解析
    main.py                   <-- API 入口
  /gui                        <-- [前端源码] Streamlit 应用
    app.py                    <-- GUI 入口
    /components               <-- UI 组件
  /prompts                    <-- Agent 提示词备份
  /scripts                    <-- 运维脚本
    bundle_for_deploy.py      <-- 打包脚本
    setup_windows.bat         <-- Windows 部署脚本
  requirements.txt            <-- 依赖清单
  .env                        <-- 环境变量
```

---

## 2. 核心系统逻辑 (保留与增强)

我们保留了经过验证的 **"管理员-文员 (Administrator-Clerk)"** 模式，并增强了数据治理能力。

### 2.1 抽取模式 (Agent 工作流)
- **StructureBot (Agent A)**: 负责“切分与归集”。建立 Site-Feature-Artifact 树，并提取全局/局部 Context Tips。
- **ExtractionBot (Agent B)**: 负责“填报”。基于动态加载的 CSV Schema + Context Tips 进行精准抽取。

### 2.2 数据双层模型 (新增)
为解决“重复上传”和“数据资产化”的矛盾，系统采用双层存储：
1.  **Staging Layer (任务层)**: 每次上传产生一个独立的 Task。数据互相隔离，允许随意删除、重试。
2.  **Master Layer (资产层)**: 用户确认无误后，执行 **Merge** 操作，将 Task 数据合并入主库。主库根据 `Site+Type+Name` 唯一性进行去重和更新。

---

## 3. Coze Bot 提示词配置

**请保持以下 Prompt 设计不变，这是系统智能的核心。**

### Bot 1: StructureBot (结构化专家)
*(参见 `prompts/agent_a_structure.md`)*
- **核心能力**: 识别实体层级、提取 `global_tips` (如"单位均为厘米") 和 `entity_tips` (如"M1被盗")。

### Bot 2: ExtractionBot (抽取专家)
*(参见 `prompts/agent_b_extraction.md`)*
- **核心能力**: 严格遵循 Schema (JSON) 进行提取，必须提供 `Quote` (原文证据)。

---

## 4. GUI 功能设计 (Streamlit 仪表盘)

系统提供可视化的操作界面，替代纯 API 调用。

1.  **任务中心 (Task Hub)**:
    -   文件上传 (支持批量)。
    -   实时进度监控 (进度条)。
    -   **"预览与入库"**: 查看抽取结果，点击按钮将数据写入 Master 库。
2.  **资产库 (Master Database)**:
    -   浏览所有已入库的实体。
    -   支持按遗址、器物类型筛选。
    -   **JSON/CSV 导出**: 导出用于分析的最终数据。
3.  **配置管理 (Settings)**:
    -   管理 Coze API Key 和 Bot ID。
    -   查看和重载 CSV 模版。

---

## 5. 实施冲刺计划

### Sprint 1: 基础建设 (已完成 ✅)
- [x] 项目结构搭建 (`src/`)
- [x] 数据库模型定义 (`sys_tasks`, `entities` 等)
- [x] 核心编排逻辑 (`orchestrator.py`)
- [x] 模版解析服务 (`parser_service.py`)
- [x] 基础 API 接口 (`/tasks`)

### Sprint 2: GUI 与交互 (当前阶段 🚀)
- **目标**: 完成前端界面开发，实现完整的“上传-抽取-查看”闭环。
- **任务**:
    1.  搭建 Streamlit 框架，实现 `gui/app.py`。
    2.  实现任务上传与进度轮询组件。
    3.  实现抽取结果的树形展示组件 (Tree View)。
    4.  集成配置管理页面。

### Sprint 3: 数据治理 (主数据合并)
- **目标**: 实现 Staging 到 Master 的数据流转。
- **任务**:
    1.  定义 `MasterEntity` 和 `MasterAttribute` 数据库模型。
    2.  实现 `MergerService`：处理去重、覆盖/补全逻辑。
    3.  在 GUI 中添加 "确认入库" 按钮及冲突处理逻辑。

### Sprint 4: 部署与优化 (进行中 🚧)
- **目标**: 针对 Windows Server 的打包与部署。
- **任务**:
    1.  编写 `scripts/bundle_for_deploy.py` (自动打包 zip)。
    2.  编写 `setup_windows.bat` (一键安装环境)。
    3.  [x] 编写 `WINDOWS_DEPLOYMENT_GUIDE.md` (部署手册)。

---

## 6. 部署方案

针对 Windows Server 2019 的无缝交付。

### 6.1 打包 (Packaging on Mac)
运行 `python scripts/bundle_for_deploy.py`，生成 `release_v3.zip`。包含：
- 完整源码 (剔除无关文件)
- `requirements.txt`
- `setup_windows.bat`
- `src/assets/` (内含最新模版)

### 6.2 部署 (Deploying on Windows)
1.  解压 `release_v3.zip`。
2.  双击 `setup_windows.bat`。脚本将自动：
    -   创建 Python 虚拟环境。
    -   安装依赖。
    -   启动 API 服务 (后台)。
    -   启动 GUI 服务 (自动打开浏览器)。

---

# English Version

# Archaeological Info Extraction System Implementation Manual (V3.1)

**Version**: 3.1 (GUI-Enhanced & Data-Governed)
**Date**: 2026-02-01
**Scenario**: Cursor Dev -> Windows Server 2019 Deployment
**Core Architecture**: Streamlit (GUI) + FastAPI (Backend) + Coze Agents (LLM)

---

## 1. Directory Structure

Based on V2.5 architecture, using separated frontend/backend but isomorphic deployment.

```text
/project_root
  /src                        <-- [Backend Source]
    /api                      <-- FastAPI Routes
    /assets                   <-- [Assets] Production CSV Templates
      template_site.csv       <-- Site Template
      template_pottery.csv    <-- Pottery Template
      ...
    /core                     <-- Config & Logging
    /db                       <-- DB Models & Init
    /services                 <-- Core Logic
      orchestrator.py         <-- Orchestrator (Admin-Clerk Mode)
      merger_service.py       <-- [New] Data Merge Service
      parser_service.py       <-- CSV Template Parser
    main.py                   <-- API Entrypoint
  /gui                        <-- [Frontend Source] Streamlit App
    app.py                    <-- GUI Entrypoint
    /components               <-- UI Components
  /prompts                    <-- Agent Prompt Backups
  /scripts                    <-- Ops Scripts
    bundle_for_deploy.py      <-- Packaging Script
    setup_windows.bat         <-- Windows Deployment Script
  requirements.txt            <-- Dependencies
  .env                        <-- Environment Variables
```

---

## 2. Core System Logic (Retained & Enhanced)

We retain the proven **"Administrator-Clerk"** pattern and enhance data governance.

### 2.1 Extraction Pattern (Agent Workflow)
- **StructureBot (Agent A)**: Responsible for "Segmentation & Aggregation". Builds Site-Feature-Artifact tree and extracts Context Tips.
- **ExtractionBot (Agent B)**: Responsible for "Filling". Performs precision extraction based on dynamically loaded CSV Schema + Context Tips.

### 2.2 Dual-Layer Data Model (New)
To resolve "Duplicate Uploads" vs "Data Asset" conflicts, we use dual-layer storage:
1.  **Staging Layer**: Each upload creates an independent Task. Data is isolated, allowing deletion and retry.
2.  **Master Layer**: After confirmation, execute **Merge** to write Task data into Master DB. Master DB deduplicates/updates based on `Site+Type+Name`.

---

## 3. Coze Bot System Prompts

**Please keep the following Prompt designs unchanged, as they are the core intelligence.**

### Bot 1: StructureBot (Structure Expert)
*(See `prompts/agent_a_structure.md`)*
- **Core Capability**: Identifies entity hierarchy, extracts `global_tips` (e.g., "units in cm") and `entity_tips` (e.g., "M1 looted").

### Bot 2: ExtractionBot (Extraction Expert)
*(See `prompts/agent_b_extraction.md`)*
- **Core Capability**: Strictly follows Schema (JSON) for extraction, must provide `Quote` (evidence).

---

## 4. GUI Dashboard Design

Visual interface replacing pure API calls.

1.  **Task Hub**:
    -   File Upload (Batch support).
    -   Real-time Progress Monitor.
    -   **"Preview & Merge"**: View extraction results, click to write to Master DB.
2.  **Asset Library (Master DB)**:
    -   Browse all merged entities.
    -   Filter by Site, Artifact Type.
    -   **JSON/CSV Export**: Export final data for analysis.
3.  **Settings**:
    -   Manage Coze API Key and Bot IDs.
    -   View and reload CSV templates.

---

## 5. Execution Sprints

### Sprint 1: Foundation (Completed ✅)
- [x] Project Structure (`src/`)
- [x] DB Models (`sys_tasks`, `entities`, etc.)
- [x] Orchestrator Logic (`orchestrator.py`)
- [x] Parser Service (`parser_service.py`)
- [x] Basic API (`/tasks`)

### Sprint 2: GUI & Interaction (Current 🚀)
- **Goal**: Complete frontend, realizing full "Upload-Extract-View" loop.
- **Tasks**:
    1.  Build Streamlit framework (`gui/app.py`).
    2.  Implement Upload & Progress Polling.
    3.  Implement Tree View for results.
    4.  Integrate Settings page.

### Sprint 3: Data Governance (Master Merger)
- **Goal**: Implement Data Flow from Staging to Master.
- **Tasks**:
    1.  Define `MasterEntity` & `MasterAttribute` models.
    2.  Implement `MergerService`: Dedup, Overwrite/Complete logic.
    3.  Add "Confirm Merge" button and conflict handling in GUI.

### Sprint 4: Deployment & Optimization
- **Goal**: Packaging & Deployment for Windows Server.
- **Tasks**:
    1.  Write `scripts/bundle_for_deploy.py`.
    2.  Write `setup_windows.bat`.
    3.  Write `README_DEPLOY.md`.

---

## 6. Deployment Strategy

Seamless delivery for Windows Server 2019.

### 6.1 Packaging (on Mac)
Run `python scripts/bundle_for_deploy.py` to generate `release_v3.zip`. Includes:
- Clean source code
- `requirements.txt`
- `setup_windows.bat`
- `src/assets/` (latest templates)

### 6.2 Deploying (on Windows)
1.  Unzip `release_v3.zip`.
2.  Double-click `setup_windows.bat`. Script auto-executes:
    -   Create Python venv.
    -   Install dependencies.
    -   Start API Service (Background).
    -   Start GUI Service (Auto-launch browser).
