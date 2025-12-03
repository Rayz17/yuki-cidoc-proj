# 缩进错误修复

## 问题描述

GUI启动时报错：
```
IndentationError: expected an indented block after 'if' statement on line 367
File: /Users/rayz/Downloads/yuki-cidoc-proj/src/automated_extractor.py, line 368
```

## 根本原因

在 `src/automated_extractor.py` 第367-372行，`if` 语句后的代码块缩进不正确：

```python
# 错误的代码
if '核心实体类型' not in artifact:
artifact['核心实体类型'] = 'E22'  # ❌ 缩进错误
```

## 修复方案

**文件**: `src/automated_extractor.py` (第367-372行)

```python
# 修复后的代码
if '核心实体类型' not in artifact:
    artifact['核心实体类型'] = 'E22'  # ✅ 正确缩进
if '关系' not in artifact:
    artifact['关系'] = 'P45 consists of'
if '中间类' not in artifact:
    artifact['中间类'] = 'E57 Material (材料)'
```

## 测试结果

```bash
✅ 所有模块导入成功
✅ GUI可以启动了
```

## 现在可以做什么

启动GUI：
```bash
streamlit run gui/app_v3.py
```

---

**修复完成！GUI现在可以正常启动了。** ✅

