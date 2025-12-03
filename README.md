# 文物文化特征单元数据抽取系统

一个基于大语言模型（LLM）的智能系统，用于从考古发掘报告中自动化抽取文物信息。

## 功能概览

-   **多模式运行**：支持命令行（CLI）和图形用户界面（GUI）两种操作模式。
-   **LLM驱动**：常态化使用大语言模型（如Claude）进行信息提取，能处理不同报告的行文差异。
-   **结构化输出**：抽取结果存储在SQLite数据库中，支持浏览和导出。
-   **灵活配置**：通过`config.json`轻松配置LLM服务和文件路径。
-   **可扩展**：支持多种文物类型和报告模板，易于扩展。

## 项目结构

```
├── config.json                   # 全局配置文件，包含LLM API Key和路径
├── main.py                      # CLI版本的主脚本
├── PROJECT_PLAN.md               # 项目开发计划和需求文档
├── README.md                     # 本文件，项目说明
├── reports/                     # 存放输入的考古报告 (.md 文件)
├── templates/                   # 存放数据结构模板 (.xlsx 文件)
├── database/                    # 存放输出的数据库 (artifacts.db)
├── prompts/                     # 存放LLM提示词模板
├── src/                         # 核心Python模块
│   ├── automated_extractor.py  # LLM抽取逻辑
│   ├── content_extractor.py    # 文本分割逻辑
│   ├── database_manager.py     # 数据库操作
│   └── report_processor.py     # 模板加载逻辑
└── gui/                         # GUI应用
    └── app.py                  # Streamlit Web应用入口
```

## 快速开始

### 前提条件

-   Python >= 3.8
-   `streamlit`, `pandas`, `openpyxl`, `sqlite3` 库

### 安装与运行 (GUI)

1.  将克隆仓库到本地。
2.  安装依赖: `pip install streamlit pandas openpyxl`
3.  将置您的LLM API Key:
    -   打开 `config.json`。
    -   将 `your-anthropic-api-key-here` 替换为您从 [Anthropic Console](https://console.anthropic.com) 获取的API Key。
4.  运行GUI应用: `streamlit run gui/app.py`

### CLI使用

```bash
python src/main.py -r reports/full.md -t templates/structure_v2.xlsx -d database/artifacts.db
```

## 使用指南

### 图形用户界面 (GUI)

1. 启动应用后，您将看到主界面包含两个选项卡："数据抽取" 和 "数据库浏览"。
2. 在侧边栏中，您可以:
   - 选择要处理的考古报告文件 (.md)
   - 选择对应的数据结构模板 (.xlsx)
   - 配置LLM服务的API URL、API Key和模型
   - 点击"保存LLM配置"以应用更改
3. 在"数据抽取"选项卡中:
   - 选择报告和模板后，点击"开始抽取"按钮
   - 系统将调用LLM服务处理报告文本
   - 处理完成后，结果将自动存入数据库
4. 在"数据库浏览"选项卡中:
   - 您可以查看数据库中的所有表格
   - 选择一个表格查看其内容
   - 使用"导出为CSV"按钮将数据导出

### 命令行界面 (CLI)

使用以下命令格式执行数据抽取:

```bash
python src/main.py [选项]
```

**必需参数:**
- `-r, --report REPORT`: 考古报告文件的路径 (例如: reports/full.md)
- `-t, --template TEMPLATE`: 数据结构模板文件的路径 (例如: templates/structure_v2.xlsx)

**可选参数:**
- `-d, --database DATABASE`: 输出数据库文件的路径 (默认: database/artifacts.db)

**使用示例:**
```bash
# 基本使用
python src/main.py -r reports/full.md -t templates/structure_v2.xlsx

# 指定输出数据库
python src/main.py -r reports/full.md -t templates/structure_v2.xlsx -d output.db
```

## 配置文件 (config.json)

`config.json` 文件包含系统的核心配置:

```json
{
  "llm": {
    "api_url": "http://llm.smart-zone-dev.gf.com.cn",
    "api_key": "48f4caf4-3472-4e9c-a32a-d7d7de3834b6",
    "model": "claude-3-5-sonnet-20240620",
    "temperature": 0.7,
    "max_tokens": 1024
  },
  "database": {
    "path": "database/artifacts.db"
  },
  "reports_dir": "reports",
  "templates_dir": "templates",
  "prompts_dir": "prompts"
}
```

您可以根据需要修改这些配置，特别是 `llm.api_key` 以使用您自己的LLM服务。

## 联系方式

如有任何问题，请提 issue.