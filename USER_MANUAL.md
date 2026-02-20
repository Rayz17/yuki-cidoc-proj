# 考古信息抽取系统操作手册 (V3.2)

本手册详细说明了如何部署、启动和操作考古信息抽取系统。系统支持 Windows Server 2019 环境部署。

---

## 1. 部署前准备

### 1.1 环境要求
- **操作系统**: Windows Server 2019 或更高版本 (也可在 macOS/Linux 开发)
- **Python**: 3.11 或更高版本
- **网络**: 能够访问外网（连接 HiAgent/Coze API）

### 1.2 获取代码包
确保你拥有最新的项目代码包（包含 `src/`, `gui/`, `scripts/`, `requirements.txt` 等）。

---

## 2. 系统部署与安装

### 2.1 自动化部署 (推荐 - Windows)
我们提供了自动化脚本，可一键完成环境配置。

1.  将代码包解压到服务器目标目录（例如 `C:\Projects\ArchaeoExtractor`）。
2.  双击运行 **`setup_windows.bat`** 脚本。
3.  脚本将自动执行以下操作：
    -   检查并创建 Python 虚拟环境 (`venv`)。
    -   安装所有依赖包 (`requirements.txt`)。
    -   初始化 SQLite 数据库 (`src/db/init_db.py`)。
    -   启动后端 API 服务。
    -   启动前端 GUI 服务并自动打开浏览器。

### 2.2 手动部署 (macOS / Linux / Windows)
如果你需要手动控制部署过程，请按以下步骤操作：

**Step 1: 创建虚拟环境**
```bash
python3 -m venv venv
# 激活环境:
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
```

**Step 2: 安装依赖**
```bash
pip install -r requirements.txt
```

**Step 3: 初始化数据库**
这将创建 `archaeo_data.db` 文件并初始化表结构。
```bash
python -m src.db.init_db
```

---

## 3. 服务启动与运行

系统分为 **后端 (API)** 和 **前端 (GUI)** 两个部分，需要同时运行。

### 3.1 启动后端服务
后端服务基于 FastAPI，负责核心逻辑处理。

在终端（已激活 venv）中运行：
```bash
python src/main.py
```
*   成功启动后，你会看到类似 `Uvicorn running on http://0.0.0.0:8000` 的日志。
*   API 文档地址: `http://localhost:8000/docs`

### 3.2 启动前端界面
前端服务基于 Streamlit，提供可视化操作界面。

新建一个终端窗口（已激活 venv），运行：
```bash
streamlit run gui/app.py
```
*   成功启动后，浏览器将自动打开 `http://localhost:8501`。

---

## 4. 系统操作指南 (GUI)

打开浏览器访问系统主页（默认 `http://localhost:8501`），左侧为导航栏。

### 4.1 系统配置 (Agent 配置)
首次使用前，需要配置 LLM Agent。

1.  点击左侧导航栏 **“系统设置”**。
2.  进入 **“Agent 资源池管理”** 标签页。
3.  **添加 Agent**:
    -   **名称**: 自定义（如 `HiAgent-Structure-1`）。
    -   **Bot ID**: 对应平台的 Bot ID / App ID (如 `d61jkb4ka0lpv10kqpdg`)。
    -   **类型**: 选择 **STRUCTURE** (结构化) 或 **EXTRACTION** (抽取)。需分别至少配置一个。
    -   **API Token**: 平台的鉴权 Token (如 `d62nm18e1f7r17ucko8g`)。
    -   **API Base URL**: 平台接口地址 (如 `https://hiagent-dev.gf.com.cn/api/proxy/api/v1`)。
4.  点击 **“添加 Agent”** 保存。列表将显示已配置的 Agent 及其状态。

### 4.2 执行抽取任务
1.  点击左侧导航栏 **“任务中心”**。
2.  **上传文件**: 将考古报告文本文件（`.txt`）拖入上传区域。支持批量上传。
3.  **开始抽取**: 上传后任务会自动创建，系统后端将自动调度 Agent A 和 Agent B 进行处理。
4.  **监控进度**:
    -   可以在任务列表中看到实时状态（`STRUCTURING` -> `EXTRACTING` -> `COMPLETED`）。
    -   点击任务左侧的 `>` 展开，可查看详细的进度条和日志。
5.  **预览与入库**:
    -   任务完成后，点击 **“预览结果”** 查看抽取的实体树和属性。
    -   确认无误后，点击 **“确认入库”**，数据将合并到主数据库（Master Data）。

### 4.3 数据资产管理
1.  点击左侧导航栏 **“数据资产库”**。
2.  这里展示了所有已确认入库的“黄金数据”（Master Data）。
3.  **筛选**: 可按“遗址名称”或“器物类型”进行筛选。
4.  **导出**: 点击右上角的 **“导出为 CSV”** 按钮，将全量资产数据下载到本地。

### 4.4 数据库管理 (高级)
1.  点击左侧导航栏 **“数据库管理”**。
2.  **表结构**: 查看当前数据库的表定义。
3.  **SQL 查询**: 输入 SQL 语句（仅限 `SELECT`）直接查询数据库。
4.  **危险操作**: 提供 **“重置数据库”** 功能，将清空所有数据（需二次确认）。

---

# English Version

# System Operation Manual (V3.2)

This manual details how to deploy, start, and operate the Archaeological Information Extraction System. It supports deployment on Windows Server 2019.

---

## 1. Preparation

### 1.1 Requirements
- **OS**: Windows Server 2019 or newer (also supports macOS/Linux).
- **Python**: 3.11 or newer.
- **Network**: Internet access required (to reach HiAgent/Coze API).

### 1.2 Get Source Code
Ensure you have the latest source package (including `src/`, `gui/`, `scripts/`, `requirements.txt`).

---

## 2. Deployment & Installation

### 2.1 Automated Deployment (Recommended - Windows)
We provide an automated script for one-click setup.

1.  Unzip the package to the target directory (e.g., `C:\Projects\ArchaeoExtractor`).
2.  Run **`setup_windows.bat`**.
3.  The script will automatically:
    -   Create a Python virtual environment (`venv`).
    -   Install dependencies (`requirements.txt`).
    -   Initialize the SQLite database (`src/db/init_db.py`).
    -   Start the Backend API service.
    -   Start the Frontend GUI service and open the browser.

### 2.2 Manual Deployment
If you need manual control:

**Step 1: Create Virtual Environment**
```bash
python3 -m venv venv
# Activate:
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
```

**Step 2: Install Dependencies**
```bash
pip install -r requirements.txt
```

**Step 3: Initialize Database**
Creates `archaeo_data.db` and tables.
```bash
python -m src.db.init_db
```

---

## 3. Starting Services

The system consists of **Backend (API)** and **Frontend (GUI)**, both must run simultaneously.

### 3.1 Start Backend
Run in a terminal (venv activated):
```bash
python src/main.py
```
*   Success: Logs show `Uvicorn running on http://0.0.0.0:8000`.
*   API Docs: `http://localhost:8000/docs`

### 3.2 Start Frontend
Run in a new terminal (venv activated):
```bash
streamlit run gui/app.py
```
*   Success: Browser opens `http://localhost:8501`.

---

## 4. Operation Guide (GUI)

Access the system homepage (default `http://localhost:8501`).

### 4.1 System Configuration (Agent Setup)
Configure LLM Agents before first use.

1.  Go to **"Settings"** (系统设置).
2.  Select **"Agent Pool Management"** tab.
3.  **Add Agent**:
    -   **Name**: Custom name (e.g., `HiAgent-Structure-1`).
    -   **Bot ID**: Platform Bot ID / App ID.
    -   **Type**: Select **STRUCTURE** or **EXTRACTION**. At least one of each is required.
    -   **API Token**: Platform API Token.
    -   **API Base URL**: Platform API endpoint.
4.  Click **"Add Agent"** to save.

### 4.2 Extraction Tasks
1.  Go to **"Task Center"** (任务中心).
2.  **Upload**: Drag & drop report text files (`.txt`). Batch upload supported.
3.  **Start**: Tasks start automatically upon upload.
4.  **Monitor**: View status (`STRUCTURING` -> `EXTRACTING` -> `COMPLETED`) and progress logs.
5.  **Preview & Merge**:
    -   Click **"Preview"** to see results.
    -   Click **"Confirm Merge"** (确认入库) to save data to the Master Database.

### 4.3 Asset Management
1.  Go to **"Master Data"** (数据资产库).
2.  View all consolidated "Golden Data".
3.  **Filter**: Filter by Site Name or Artifact Type.
4.  **Export**: Click **"Export to CSV"** to download all data.

### 4.4 Database Tools (Advanced)
1.  Go to **"Database Management"** (数据库管理).
2.  **Schema**: View table definitions.
3.  **SQL Query**: Run read-only SQL queries.
4.  **Reset**: Wipe all data (Reset Database).
