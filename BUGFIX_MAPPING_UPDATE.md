# 字段映射修复 (Field Mapping Fix)

## 问题描述
用户报告错误：`table pottery_artifacts has no column named additives`。
这表明 LLM 抽取了 `additives` 字段（对应中文“掺杂物”），但数据库中没有该列（实际上是 `mixed_materials`）。

## 原因分析
Excel 模板中的字段名（如“陶土种类”、“掺杂物”、“人工物品编号”）与代码中的预定义映射表不匹配。
导致 `TemplateAnalyzer` 无法正确将这些中文字段映射到数据库已有的英文字段，而是可能生成了错误的字段名（或 LLM 自行翻译为 additives）。

## 修复方案
更新了 `src/template_analyzer.py` 中的映射表，添加了新模板中使用的字段名：

```python
'陶土种类': 'clay_type',
'陶土纯洁程度': 'clay_purity',
'掺杂物': 'mixed_materials',
'基本器型': 'basic_shape',
'人工物品编号': 'artifact_code',
...
```

## 验证
Prompt 现在将生成正确的英文字段名（如 `mixed_materials`），LLM 将返回正确的 Key，或者返回中文 Key 后能被 `FieldMapper` 正确映射。

---

**请重新运行抽取任务以验证修复效果。** 🚀

