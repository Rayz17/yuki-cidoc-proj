# BUGFIX: GUI Nested Expander & Task Queue Visibility

**日期**: 2025-12-02
**状态**: ✅ 已修复

## 问题描述

1. **Streamlit 报错**: `streamlit.errors.StreamlitAPIException: Expanders may not be nested inside other expanders.`
   - **原因**: 在任务列表的 `st.expander` 内部（显示任务详情时），如果检测到失败的响应文件，又尝试创建一个 `st.expander` 来显示恢复工具。Streamlit 不支持嵌套 Expander。
   - **触发场景**: 当任务处于运行或展开状态，且存在 `failed_responses` 日志文件时。

2. **任务队列不可见**:
   - **现象**: 当用户提交的任务数量（如7个）超过并发限制（如5个Bot）时，排队的任务（2个）在 GUI 列表中不显示，直到它们开始执行。
   - **原因**: 原逻辑中，`BatchScheduler` 是在线程池开始执行任务时（`_run_single_task` 内部）才调用 `ExtractionWorkflow.create_task` 创建数据库记录。排队中的任务尚未创建数据库记录，因此 GUI 无法从数据库查看到它们。

3. **网络波动报错**:
   - **现象**: 抽取过程中网络变化会导致报错。
   - **原因**: Streamlit 在网络波动时可能会重新运行脚本，触发上述渲染逻辑，导致 UI 崩溃。修复嵌套 expander 可以解决此 UI 崩溃问题。

## 解决方案

### 1. GUI 修复 (`gui/app_v3.py`)

- 将内部的 `st.expander` 替换为 `st.markdown` 标题 + `st.container`。
- 保持了 "异常响应恢复" 功能的可用性，同时避免了 UI 嵌套错误。

```python
# Before
with st.expander(f"⚠️ 发现 {len(failed_files)} 个异常响应 (可尝试恢复)", expanded=True):
    ...

# After
st.markdown(f"#### ⚠️ 发现 {len(failed_files)} 个异常响应 (可尝试恢复)")
with st.container():
    ...
```

### 2. 调度器优化 (`src/scheduler.py`)

- 修改 `execute_batch` 方法：
    1. **预创建任务**: 在提交到线程池之前，先实例化 `ExtractionWorkflow` 并循环调用 `create_task`，将所有任务记录写入数据库，状态默认为 `pending`。
    2. **传递 Task ID**: 将预生成的 `task_id` 传递给 `_run_single_task`。

### 3. 工作流调整 (`src/workflow.py`)

- 将 `_create_task` 重构为公开方法 `create_task`。
- 更新 `execute_full_extraction` 方法签名，增加可选参数 `task_id`。
- 如果传入了 `task_id`，则跳过创建步骤，直接使用该 ID 并更新状态为 `running`。

## 验证结果

- **UI 稳定性**: 即使有失败响应文件，任务列表也能正常展开，不再报错。
- **队列可见性**: 点击 "开始批量抽取" 后，所有任务立即出现在 "任务管理" 列表中（显示为白色/pending 状态），随后并发任务变为蓝色（running），排队任务保持 pending 直到有空闲 Bot。

