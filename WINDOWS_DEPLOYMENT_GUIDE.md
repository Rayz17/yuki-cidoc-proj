# Windows Server 2019 部署手册 (Deployment Manual)

本手册详细说明如何将 Yuki CIDOC 项目部署到 Windows Server 2019 环境中。

## 1. 环境准备 (Prerequisites)

在开始部署之前，请确保服务器满足以下要求：

### 1.1 基础软件安装
1.  **Python 3.10+**:
    *   下载并安装 Python 3.10 或更高版本 (建议 3.11)。
    *   **重要**: 安装时务必勾选 "Add Python to PATH" (将 Python 添加到环境变量)。
2.  **Git (可选)**:
    *   如果需要通过 Git 拉取代码，请安装 Git for Windows。
    *   如果不使用 Git，可以通过压缩包将代码上传到服务器。
3.  **Neo4j (可选)**:
    *   如果项目需要使用图数据库功能，请安装 **Neo4j Desktop** 或 **Neo4j Server Community Edition**。
    *   确保 Neo4j 服务已启动，并记录下连接地址 (通常为 `bolt://localhost:7687`) 和密码。

### 1.2 网络配置
*   确保服务器防火墙允许以下端口的入站连接（如果需要从外部访问）：
    *   **8000**: 后端 API 服务端口
    *   **8501**: 前端 GUI 服务端口

---

## 2. 代码部署 (Deployment)

### 2.1 获取代码
将项目代码复制到服务器上的目标目录，例如 `C:\Projects\yuki-cidoc-proj`。

### 2.2 创建虚拟环境 (Virtual Environment)
建议使用虚拟环境来隔离项目依赖，避免与系统 Python 冲突。

打开 PowerShell 或 CMD，进入项目目录：

```powershell
cd C:\Projects\yuki-cidoc-proj

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境 (PowerShell)
.\venv\Scripts\Activate.ps1
# 或者 (CMD)
.\venv\Scripts\activate.bat
```

### 2.3 安装依赖 (Dependencies)
在激活的虚拟环境中，安装项目所需的 Python 库：

```powershell
pip install --upgrade pip
pip install -r requirements.txt
```

> **注意**: 如果安装 `asyncpg` 或其他库时遇到编译错误，通常是因为缺少 C++ 构建工具。对于 Windows Server，可以直接下载对应库的 `.whl` 文件安装，或者安装 "Microsoft C++ Build Tools"。但在大多数情况下，预编译的二进制包（binary wheels）应该可以直接安装。

---

## 3. 系统配置 (Configuration)

### 3.1 环境变量配置 (.env)
在项目根目录下创建一个名为 `.env` 的文件（如果不存在），并根据实际情况配置以下内容：

```ini
# .env 文件示例

# 项目基础设置
PROJECT_NAME="Archaeo Extractor V3.5"
API_V1_STR="/api/v1"

# 数据库设置 (默认使用 SQLite，无需修改即可运行)
DATABASE_URL="sqlite:///./archaeo_data.db"

# Coze API 设置 (必须配置)
COZE_API_KEY="your_coze_api_key_here"
COZE_API_BASE="https://api.coze.com/open_api/v2"

# Bot ID 配置 (根据实际 Bot ID 填写)
COZE_BOT_ID_A="your_structure_bot_id"
COZE_BOT_ID_B="your_extraction_bot_id"
COZE_BOT_ID_C="your_dedup_bot_id"

# Redis 设置 (可选，如果未安装 Redis 可忽略或注释掉)
# REDIS_URL="redis://localhost:6379/0"
```

### 3.2 数据库初始化
项目启动时会自动检查并创建 SQLite 数据库表结构，无需手动初始化 SQL。

---

## 4. 启动服务 (Running the System)

系统由两个部分组成：后端 API 和前端 GUI。需要分别启动这两个服务。

### 4.1 启动后端 API
打开一个新的 PowerShell 窗口，进入项目目录并激活虚拟环境：

```powershell
cd C:\Projects\yuki-cidoc-proj
.\venv\Scripts\Activate.ps1

# 启动后端服务 (生产环境建议不加 --reload)
uvicorn src.main:app --host 0.0.0.0 --port 8000
```

看到 `Application startup complete` 即表示后端启动成功。

### 4.2 启动前端 GUI
打开另一个 PowerShell 窗口，进入项目目录并激活虚拟环境：

```powershell
cd C:\Projects\yuki-cidoc-proj
.\venv\Scripts\Activate.ps1

# 启动前端应用
streamlit run gui/app.py --server.port 8501
```

启动后，可以通过浏览器访问 `http://localhost:8501` (或服务器 IP:8501) 使用系统。

---

## 5. 自动化运行 (Automation)

为了方便管理，建议创建一个批处理脚本 (`start_system.bat`) 来一键启动所有服务。

### 5.1 创建启动脚本
在项目根目录下创建 `start_system.bat`：

```batch
@echo off
cd /d %~dp0

echo Starting Backend API...
start "Backend API" cmd /k "venv\Scripts\activate.bat && uvicorn src.main:app --host 0.0.0.0 --port 8000"

echo Waiting for Backend to initialize...
timeout /t 5

echo Starting Frontend GUI...
start "Frontend GUI" cmd /k "venv\Scripts\activate.bat && streamlit run gui/app.py --server.port 8501"

echo System Started!
```

双击该脚本即可启动系统。

### 5.2 (进阶) 设置为 Windows 服务
如果希望系统在服务器重启后自动运行，可以使用 **NSSM (Non-Sucking Service Manager)** 将 Python 脚本注册为服务。

1.  下载 NSSM 并解压。
2.  运行安装命令：
    ```powershell
    nssm install YukiBackend
    ```
3.  在弹出的窗口中：
    *   **Path**: 选择虚拟环境中的 `python.exe` (例如 `C:\Projects\yuki-cidoc-proj\venv\Scripts\python.exe`)
    *   **Startup directory**: 项目根目录
    *   **Arguments**: `-m uvicorn src.main:app --host 0.0.0.0 --port 8000`
4.  点击 "Install service"。
5.  同样步骤安装 `YukiFrontend`，Arguments 为 `-m streamlit run gui/app.py --server.port 8501`。
6.  在服务管理器中启动这两个服务。

---

## 6. 常见问题 (FAQ)

*   **Q: 启动时提示 `ModuleNotFoundError`?**
    *   A: 请检查是否已激活虚拟环境，并且执行了 `pip install -r requirements.txt`。
*   **Q: 无法访问 8000 或 8501 端口?**
    *   A: 请检查 Windows 防火墙设置，确保添加入站规则允许 TCP 端口 8000 和 8501。
*   **Q: 数据库文件在哪里?**
    *   A: 默认情况下，`archaeo_data.db` 文件会生成在项目根目录下。请定期备份该文件。
