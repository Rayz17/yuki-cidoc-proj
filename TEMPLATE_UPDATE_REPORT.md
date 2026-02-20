# 抽取模版更新与完善报告

**更新时间**: 2026-01-18
**更新文件**: `@yuki-ref/抽取模版clean_0118.csv`
**参考语料**: `@yuki-ref/30reports-for-enhancing-dictionary` (33份考古发掘报告)

## 1. 工作概述

针对抽取模版中 J（字典定义）、K（原文术语）、L（转写规则）、M（同义词）四列内容缺失或待补充的情况，进行了系统的分析与完善。

通过编写自动化脚本，对 30+ 份报告进行全文扫描，提取高频术语，并结合 CIDOC CRM 与考古学分类体系，构建了从“原文描述”到“标准化编码”的完整映射链条。

## 2. 详细变更内容

### 2.1 J 列：字典与定义完善 (Dictionary & Definition)

针对原有标记为“待补充”或定义模糊的指标，完成了以下核心更新：

*   **陶器形态**: 细化了 P2/P3 的形态与高度特征，确立了标准值集。
*   **保存状况**: 完善了 PSD3-5 的结构、表面及断口保存状况字典。
*   **玉器材质**: 明确了有机及次生变化（如鸡骨白）的分类编码。
*   **表面工艺**: 扩充了陶衣及彩绘的详细字典。

### 2.2 K 列：原文术语示例丰富 (Original Terms Enrichment)

基于报告语料提取真实高频词汇（Top 15）：

*   **成果**: 填充约 **37** 个核心分类指标的真实用例。
*   **示例**: `泥质灰`、`云雷纹`、`侈口`、`透闪石`、`单面钻` 等。

### 2.3 L 列：转写规则构建 (Transcription Rules)

采用**语义映射 + 理论推导**策略，生成全量指标规则（覆盖率 > 85%）：

*   **Categorical**: `中文术语 -> 标准编码` (e.g. `聚落 -> ST1`)
*   **Numerical**: `提取数值 (e.g. "高15cm" -> 15)`
*   **Text**: `提取原文描述`
*   **Boolean**: `是 -> True; 否 -> False`

### 2.4 M 列：同义词扩充 (Synonym Examples)

通过多源融合策略，构建了丰富的同义词库（覆盖 ~160 行）：

1.  **指标同义词**: 预置考古学常用字段别名。
    *   例: `器物名称: 器名, 定名`; `通高: 器高, 残高`
2.  **英汉同义词**: 从字典定义中提取英文术语。
    *   例: `红陶: Red ware`; `玉礼器: Ritual jades`
3.  **L-Mapping 同义词**: 自动聚类 L 列中指向同一编码的不同术语。
    *   例: `P2F101: 束颈, 细颈, 收颈`

## 3. 统计数据

*   **核心指标定义更新**: ~40 行
*   **原文示例填充 (K)**: ~37 行
*   **转写规则生成 (L)**: ~254 行
*   **同义词库扩充 (M)**: ~163 行

## 4. 后续建议

*   当前模版已具备较好的“冷启动”能力，但在实际抽取中，对于复合描述（如“侈口束颈鼓腹”）仍需依赖 LLM 的组合推理能力，模版中的规则主要作为 Prompt 的 Few-shot 示例存在。
*   建议在抽取 Pipeline 中加入“未命中术语挖掘”机制，持续回流新出现的术语到 K 列。

---

# English Version

# Extraction Template Update and Improvement Report

**Update Date**: 2026-01-18
**Updated File**: `@yuki-ref/抽取模版clean_0118.csv`
**Reference Corpus**: `@yuki-ref/30reports-for-enhancing-dictionary` (33 archaeological excavation reports)

## 1. Work Overview

Analyzed and improved the J (Dictionary Definition), K (Original Terms), L (Transcription Rules), and M (Synonyms) columns where content was missing or needed supplementation.

Automated scripts scanned 30+ reports to extract high-frequency terms, combined with CIDOC CRM and archaeological classification systems, building a complete mapping chain from "original description" to "standardized code".

## 2. Detailed Changes

### 2.1 Column J: Dictionary & Definition

Refined indicators marked as "to be supplemented" or with vague definitions:

*   **Pottery Shape**: Refined P2/P3 shape and height features, established standard value sets.
*   **Condition**: Improved dictionaries for PSD3-5 structure, surface, and fracture conditions.
*   **Jade Material**: Clarified classification codes for organic and secondary changes (e.g., chicken bone white).
*   **Surface Craft**: Expanded detailed dictionaries for slip and painting.

### 2.2 Column K: Original Terms Enrichment

Extracted real high-frequency terms (Top 15) from report corpus:

*   **Result**: Filled real cases for about **37** core classification indicators.
*   **Examples**: `Fine gray clay` (泥质灰), `Cloud and thunder pattern` (云雷纹), `Flared mouth` (侈口), `Tremolite` (透闪石), `Single-side drilling` (单面钻), etc.

### 2.3 Column L: Transcription Rules

Adopted **Semantic Mapping + Theoretical Deduction** strategy to generate full indicator rules (Coverage > 85%):

*   **Categorical**: `Chinese Term -> Standard Code` (e.g. `Settlement -> ST1`)
*   **Numerical**: `Extract Value (e.g. "Height 15cm" -> 15)`
*   **Text**: `Extract original description`
*   **Boolean**: `Yes -> True; No -> False`

### 2.4 Column M: Synonym Examples

Built a rich synonym database through multi-source fusion (Covering ~160 rows):

1.  **Indicator Synonyms**: Preset common aliases for archaeological fields.
    *   Example: `Artifact Name: Object Name, Designation`; `Total Height: Vessel Height, Residual Height`
2.  **English-Chinese Synonyms**: Extracted English terms from dictionary definitions.
    *   Example: `Red pottery: Red ware`; `Jade Ritual Object: Ritual jades`
3.  **L-Mapping Synonyms**: Automatically clustered different terms pointing to the same code in Column L.
    *   Example: `P2F101: Constricted neck, Thin neck, Narrow neck`

## 3. Statistics

*   **Core Indicator Definition Updates**: ~40 rows
*   **Original Example Filling (K)**: ~37 rows
*   **Transcription Rule Generation (L)**: ~254 rows
*   **Synonym Database Expansion (M)**: ~163 rows

## 4. Future Recommendations

*   The current template has good "cold start" capabilities, but for compound descriptions (e.g., "flared mouth, constricted neck, drum belly"), it still relies on LLM's combinatorial reasoning. Rules in the template mainly serve as Few-shot examples in Prompts.
*   Suggest adding a "Missed Term Mining" mechanism in the extraction pipeline to continuously feed back new terms to Column K.
