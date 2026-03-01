# Yuki CIDOC 项目上下文

> 此文档为 Claude Code 提供项目背景信息，便于后续协助开发和维护。

## 1. 项目概述

| 项目 | 说明 |
|------|------|
| **名称** | Yuki CIDOC / Archaeo Extractor V3.5 |
| **用途** | 考古文献数据提取与知识图谱构建系统 |
| **位置** | `C:\Projects\yuki-cidoc-proj` |
| **Git 仓库** | https://github.com/Rayz17/yuki-cidoc-proj.git |
| **分支** | main |

## 2. 技术架构

```
┌─────────────────────────────────────────────────────┐
│                   前端 GUI                          │
│              Streamlit (端口 8501)                  │
│              gui/app.py                             │
└─────────────────────┬───────────────────────────────┘
                      │ HTTP API
┌─────────────────────▼───────────────────────────────┐
│                   后端 API                          │
│              FastAPI/Uvicorn (端口 8000)            │
│              src/main.py                            │
└─────────────────────┬───────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                   数据层                            │
│              SQLite (archaeo_data.db)               │
│              Neo4j (可选，图数据库)                  │
└─────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────┐
│                   外部服务                          │
│              Hiagent API (LLM 调用)                 │
│              https://hiagent-dev.gf.com.cn          │
└─────────────────────────────────────────────────────┘
```

## 3. 服务管理

### 3.1 启动命令

```powershell
# 进入项目目录
cd C:\Projects\yuki-cidoc-proj

# 激活虚拟环境
.\venv\Scripts\Activate.ps1

# 启动后端 API
uvicorn src.main:app --host 0.0.0.0 --port 8000

# 启动前端 GUI (新窗口)
streamlit run gui/app.py --server.port 8501
```

### 3.2 服务端口

| 服务 | 端口 | 说明 |
|------|------|------|
| 后端 API | 8000 | FastAPI RESTful 服务 |
| 前端 GUI | 8501 | Streamlit Web 界面 |
| Neo4j (可选) | 7687 | 图数据库 bolt 协议 |

### 3.3 常用检查命令

```powershell
# 检查服务状态
netstat -ano | findstr "8000 8501"

# 检查 Python 进程
tasklist | findstr python

# 停止后端服务 (替换 PID)
taskkill /PID <PID> /F
```

## 4. 数据库结构

### 4.1 主要表

| 表名 | 说明 |
|------|------|
| `sys_tasks` | 任务管理 |
| `entities` | 提取的实体数据 |
| `entity_attributes` | 实体属性 |
| `text_segments` | 文本段关联 |
| `master_entities` | 实体主数据 |
| `master_attributes` | 属性主数据 |
| `agent_configs` | Agent 配置 |
| `system_settings` | 系统设置 |

### 4.2 sys_tasks 表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| id | CHAR(36) | 任务 ID (主键) |
| file_path | VARCHAR(255) | 上传文件路径 |
| status | VARCHAR(50) | 任务状态 |
| progress | TEXT | 进度 JSON |
| bot_structure_id | VARCHAR(100) | 结构化 Bot ID |
| bot_extraction_id | VARCHAR(100) | 提取 Bot ID |
| global_context_tips | TEXT | 全局上下文/错误日志 |
| start_time | DATETIME | 开始时间 |
| end_time | DATETIME | 结束时间 |
| is_paused | BOOLEAN | 是否暂停 |

### 4.3 任务状态流转

```
PENDING → QUEUED → STRUCTURING → EXTRACTING → COMPLETED
                ↓                ↓
            SUSPENDED        FAILED / STOPPED
```

| 状态 | 说明 | 可恢复 |
|------|------|--------|
| PENDING | 等待中 | - |
| QUEUED | 已入队 | - |
| STRUCTURING | 结构化处理中 | 是 |
| EXTRACTING | 实体提取中 | 是 |
| COMPLETED | 已完成 | - |
| SUSPENDED | 挂起 (网络错误等) | ✅ 是 |
| FAILED | 失败 | ✅ 是 |
| STOPPED | 已停止 | ✅ 是 |

## 5. Hiagent Bot 配置

### 5.1 Bot 列表

| Bot 名称 | Token | App ID | 用途 |
|----------|-------|--------|------|
| cidoc-A-1 | d62nm18e1f7r17ucko8g | d61jkb4ka0lpv10kqpdg | 结构化 |
| cidoc-B-1 | d62okd8e1f7r17uckrmg | d62oitska0lpv10kri8g | 提取 |
| cidoc-A-2 | d64aafoe1f7r17ucmn3g | d63gj3ska0lpv10kt9j0 | 结构化 |
| cidoc-B-2 | d64abt4ka0lpv10ktfn0 | d63gj8kka0lpv10kt9lg | 提取 |
| cidoc-A-3 | d67fpdcka0lpv10kul00 | d67fnrkka0lpv10kukn0 | 结构化 |
| cidoc-B-3 | d67fqikka0lpv10kul7g | d67fnu4ka0lpv10kukpg | 提取 |
| cidoc-A-4 | d67fr3ge1f7r17uco3vg | d67fof4ka0lpv10kuks0 | 结构化 |
| cidoc-B-4 | d67fri8e1f7r17uco45g | d67fohcka0lpv10kukug | 提取 |
| cidoc-C-1 | d67jafkka0lpv10kuljg | d67ip6ge1f7r17uco4a0 | 去重 |
| cidoc-C-2 | d67jcbcka0lpv10kulog | d67jc6ge1f7r17uco4hg | 去重 |

### 5.2 API 端点

- **Base URL**: `https://hiagent-dev.gf.com.cn/api/proxy/api/v1`
- **Chat API**: `/chat_query_v2`

## 6. 关键代码文件

| 文件 | 说明 |
|------|------|
| `src/main.py` | FastAPI 入口 |
| `src/db/database.py` | 数据库连接配置 |
| `src/db/models.py` | 数据模型定义 |
| `src/services/orchestrator.py` | 任务调度核心逻辑 |
| `src/services/parser_service.py` | 解析服务 |
| `gui/app.py` | Streamlit 前端主文件 |
| `gui/utils/api_client.py` | 前端 API 客户端 |

## 7. 环境配置 (.env)

```ini
PROJECT_NAME="Archaeo Extractor V3.5"
API_V1_STR="/api/v1"
DATABASE_URL="sqlite:///./archaeo_data.db"

# Hiagent API 配置
# (实际配置存储在数据库 agent_configs 表中)
```

## 8. 常见问题处理

### 8.1 任务失败 - 500 Internal Server Error

**现象**: Hiagent API 返回 500 错误

**原因**: Hiagent 服务端问题，非本地网络问题

**解决**: 等待服务恢复后，在前端界面点击"恢复"按钮重试

### 8.2 编码问题

项目已配置:
- SQLite WAL 模式
- PYTHONUTF8 环境变量
- CSV 强制 UTF-8 编码

### 8.3 查询任务详情

```python
# 使用 Python 查询任务
import sqlite3
conn = sqlite3.connect('C:/Projects/yuki-cidoc-proj/archaeo_data.db')
cursor = conn.cursor()
cursor.execute("SELECT id, status, progress FROM sys_tasks WHERE status != 'COMPLETED'")
for row in cursor.fetchall():
    print(row)
conn.close()
```

## 9. 更新记录

| 日期 | 提交 | 说明 |
|------|------|------|
| 2026-02-21 | 9124839 | Fix Windows deployment issues: UTF-8, SQLite WAL |
| - | 7f15013 | Clean up duplicate neo4j import folders |

## 10. 已知问题：GUI 数据导出内存溢出

### 10.1 问题描述

**现象**: 在 GUI 界面导出数据时，内存和 CPU 飙升，程序崩溃

**影响范围**:
- 任务详情页导出 CSV (`gui/app.py` 第 343-354 行)
- 数据资产库导出全部 (`gui/app.py` 第 450-464 行)

### 10.2 原因分析

**数据量统计** (2026-02-24):

| 表 | 记录数 |
|----|--------|
| entities | 20,553 |
| entity_attributes | 506,825 |
| master_entities | 10,611 |
| master_attributes | 398,895 |

单任务最大 CSV 行数: **137,193 行**

**问题代码位置**:

1. `src/api/tasks.py` 第 276-337 行 (`export_task_csv`):
```python
# 问题1: 一次性查询所有数据到内存
entities = db.query(Entity).filter(Entity.task_id == task_id).all()

# 问题2: 在内存中构建完整 CSV
output = io.StringIO()
for entity in entities:
    # ... 遍历所有属性，写入 StringIO
output.getvalue()  # 全部加载到内存返回
```

2. `src/api/master.py` 第 11-66 行 (`export_master_entities`):
```python
# 同样的问题：一次性加载 + 内存构建
entities = query.order_by(MasterEntity.updated_at.desc()).all()
output = io.StringIO()
# ...
```

**根本原因**:
1. **无分批处理** - 一次性 SQL 查询所有数据
2. **内存构建 CSV** - StringIO 把全部数据加载到内存
3. **N+1 查询** - 遍历实体时逐个查询属性 (relationship 延迟加载)
4. **GUI 双重消耗** - Streamlit 接收响应 + 渲染 = 内存翻倍

### 10.3 建议修复方案

**方案 A: 流式导出 (推荐)**

```python
from fastapi.responses import StreamingResponse
import csv

def generate_csv_stream(task_id: str, db: Session):
    """生成器：分批查询，流式输出"""
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=[...])
    writer.writeheader()
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)

    # 分批查询，每次 1000 条
    batch_size = 1000
    offset = 0
    while True:
        entities = db.query(Entity)\
            .filter(Entity.task_id == task_id)\
            .offset(offset).limit(batch_size).all()
        if not entities:
            break

        for entity in entities:
            # 使用 JOIN 一次性获取属性，避免 N+1
            attrs = db.query(EntityAttribute)\
                .filter(EntityAttribute.entity_id == entity.id).all()
            for attr in attrs:
                writer.writerow({...})
                yield output.getvalue()
                output.seek(0)
                output.truncate(0)

        offset += batch_size

@router.get("/{task_id}/export")
def export_task_csv(task_id: str, db: Session = Depends(get_db)):
    return StreamingResponse(
        generate_csv_stream(task_id, db),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=task_{task_id}.csv"}
    )
```

**方案 B: 后台导出 + 下载链接**

1. 点击导出后，创建后台任务
2. 生成 CSV 保存到 `exports/` 目录
3. 完成后显示下载链接
4. 定期清理过期导出文件

**方案 C: 限制导出范围**

- 添加日期范围筛选
- 添加最大行数限制 (如 50,000 行)
- 超出时提示用户使用数据库直接导出

### 10.4 临时解决方案

**推荐: 按原始文件名批量导出**

使用 Python 脚本导出最近 N 个已完成任务，CSV 文件名使用原始 md 文件名 (已验证可用):

```python
import sqlite3
import csv
import os
import json

conn = sqlite3.connect('C:/Projects/yuki-cidoc-proj/archaeo_data.db')
cursor = conn.cursor()

# 获取最近完成的 N 个任务
cursor.execute('''
SELECT id, target_files, file_path FROM sys_tasks
WHERE status = 'COMPLETED'
ORDER BY created_at DESC
LIMIT 6
''')
tasks = cursor.fetchall()

desktop = 'C:/Users/Administrator/Desktop'

for task_id, target_files, file_path in tasks:
    # 获取原始文件名
    original_name = 'unknown'
    if target_files:
        try:
            files_list = json.loads(target_files)
            if files_list and isinstance(files_list[0], dict):
                original_name = files_list[0].get('original', 'unknown')
            elif files_list:
                original_name = files_list[0]
        except:
            pass
    elif file_path:
        original_name = os.path.basename(file_path)

    # 去掉扩展名，加上.csv
    base_name = os.path.splitext(original_name)[0]
    csv_name = f'{base_name}.csv'

    # 查询数据
    cursor.execute('''
        SELECT e.id, e.parent_id, e.name, e.entity_type, e.entity_specific_tips,
               ea.attribute_code, ea.attribute_value, ea.quote, ea.confidence
        FROM entities e
        LEFT JOIN entity_attributes ea ON ea.entity_id = e.id
        WHERE e.task_id = ?
        ORDER BY e.id, ea.attribute_code
    ''', (task_id,))

    rows = cursor.fetchall()

    # 写入CSV
    filename = os.path.join(desktop, csv_name)
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        writer.writerow(['Entity ID', 'Parent ID', 'Name', 'Type', 'Tips',
                        'Attribute Code', 'Attribute Value', 'Quote', 'Confidence'])
        writer.writerows(rows)

    print(f'Exported {len(rows)} rows to {csv_name}')

conn.close()
```

**简单版本 (按 task_id 单个导出)**:

```python
import sqlite3
import csv

conn = sqlite3.connect('C:/Projects/yuki-cidoc-proj/archaeo_data.db')
cursor = conn.cursor()

task_id = 'your_task_id_here'
cursor.execute('''
    SELECT e.id, e.name, e.entity_type, ea.attribute_code, ea.attribute_value, ea.quote
    FROM entities e
    LEFT JOIN entity_attributes ea ON ea.entity_id = e.id
    WHERE e.task_id = ?
''', (task_id,))

with open('export.csv', 'w', newline='', encoding='utf-8-sig') as f:
    writer = csv.writer(f)
    writer.writerow(['ID', 'Name', 'Type', 'Attr Code', 'Attr Value', 'Quote'])
    writer.writerows(cursor.fetchall())

conn.close()
```

---

*此文档由 Claude Code 生成，用于项目上下文管理*
