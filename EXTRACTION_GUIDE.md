# 考古信息抽取操作指南

本指南旨在说明如何利用 `@yuki-ref/抽取模版clean_0118.csv` 进行高效、准确的考古报告信息抽取。

## 1. 模版逻辑与结构

### 1.1 核心概念
*   **CAU (Culture Attributes Unit)**: 抽取的顶层对象（如：`玉器 jade`、`陶器 pottery`、`遗址 site`）。所有抽取工作应以 CAU 为单位进行切分。
*   **指标层级 (L1-L3)**:
    *   **L1 (一级指标)**: 业务大类（如：`器型单元`）。
    *   **L2 (二级指标)**: 具体属性族（如：`颈部特征`）。
    *   **L3 (三级指标)**: 最细粒度的属性（如：`颈部形态`）。
*   **J-K-L-M 知识链**:
    *   **J (字典)**: 标准值的定义集合。
    *   **K (语料)**: 真实报告中的例句。
    *   **L (规则)**: `原文 -> 代码` 的映射逻辑。
    *   **M (同义)**: `标准词: 异形词` 的同义词库。

### 1.2 值类型 (Value Types)
*   **唯一值**: 必须从 J 列字典中选择**一个**代码。
*   **多值**: 可以从 J 列字典中选择**多个**代码。
*   **数量值**: 提取具体数字（通常带单位）。
*   **文本**: 提取原文描述。
*   **属性族**: 这是一个容器节点，**不要直接填值**，而应去填写其下的 L2 或 L3 子节点。

---

## 2. 抽取策略 (Extraction Strategy)

建议采用 **“分层检索 + 语义映射”** 的 Two-Stage 策略。

### Stage 1: 实体识别与上下文定位
*   **输入**: 整个报告文本。
*   **任务**: 识别出报告中描述了哪些具体的器物个体（Objects）。
*   **输出**: 器物列表及其对应的文本段落（Context Snippet）。

### Stage 2: 属性抽取 (针对每个器物)
*   **输入**: 器物文本段落 + 抽取模版（Prompt Context）。
*   **原则**:
    1.  **最细粒度优先**: 如果模版中有 `JCF01 佩饰类` 和 `JCT0101 玉璜`，且文本明确提到了“玉璜”，**只填写** `JCT0101`，系统可自动向上推导它属于 `JCF01`。
    2.  **依据 L 列规则**: 将 L 列的 `Term -> Code` 规则作为 Few-shot 示例喂给 LLM。
    3.  **处理多值**: 对于“功能”或“保存状况”，如果原文涉及多项，输出为列表（如 `['FT101', 'FT104']`）。

---

## 3. Prompt 设计示范

针对 LLM 的 Prompt 结构建议如下：

```markdown
# Role
你是一名资深的考古数据专家。

# Task
从给定的【考古报告片段】中，提取结构化数据，填入【目标字段】。

# Context
报告片段: "...该器物为泥质灰陶，侈口束颈，口径15cm，主要用于炊煮..."

# Target Fields Definition (From CSV)
1. 陶土种类 (ClayFabricType):
   - Dictionary: PS1: Fine clay ware 泥质; PS2: Sand-tempered 夹砂...
   - Rules: 泥质->PS1; 夹砂->PS2
2. 口沿方向 (Rim direction):
   - Dictionary: P1A301: 外撇; P1A304: 侈口...
   - Rules: 侈口->P1A304
3. 颈部形态 (Neck Shape):
   - Dictionary: P2F101: 束颈...
   - Rules: 束颈->P2F101

# Output Requirement
请以 JSON 格式输出，Key 为字段ID，Value 为提取到的 **代码 (Code)**。如果提取到数值，请直接输出数字。

# Your Output
{
  "ClayFabricType": "PS1",
  "P1F3": "P1A304",
  "P2F1": "P2F101",
  "MT201": 15
}
```

---

## 4. 后处理与归一化 (Post-Processing)

由于 LLM 偶尔会输出中文名称而非代码，建议编写一个**归一化脚本**：

1.  **加载映射表**: 读取 CSV 的 `L` 列和 `M` 列，构建 `Term -> Code` 的查找表。
2.  **清洗输出**: 遍历 LLM 返回的 JSON。
    *   如果 Value 是代码（如 `PS1`），保留。
    *   如果 Value 是中文（如 `泥质`），查表转换为 `PS1`。
    *   如果 Value 是同义词（如 `红褐陶`），通过 M 列找到标准词 `红陶`，再转为 `BC1`。

## 5. 常见问题处理

*   **父子节点冲突**: 如果 LLM 同时输出了父节点（如 `属性族`）和子节点的值，**保留子节点，丢弃父节点值**。
*   **单位换算**: 模版中默认长度单位为 `mm` 或 `cm`。建议统一在 Prompt 中要求输出 `cm` 或 `mm`，或者在后处理中进行正则提取和换算。
*   **未知值**: 如果原文未提及，输出 `null` 或忽略该字段，不要强行填入“未知”。只有在原文明确说“不仅详”时才填 `Unknown` 代码。

---

# English Version

# Extraction Operational Guide

This guide explains how to use `@yuki-ref/抽取模版clean_0118.csv` for efficient and accurate archaeological report information extraction.

## 1. Template Logic & Structure

### 1.1 Core Concepts
*   **CAU (Culture Attributes Unit)**: The top-level object for extraction (e.g., `jade`, `pottery`, `site`). All extraction work should be segmented by CAU.
*   **Indicator Hierarchy (L1-L3)**:
    *   **L1 (Level 1)**: Business Category (e.g., `Vessel Shape Unit`).
    *   **L2 (Level 2)**: Specific Attribute Family (e.g., `Neck Features`).
    *   **L3 (Level 3)**: Finest Granularity Attribute (e.g., `Neck Shape`).
*   **J-K-L-M Knowledge Chain**:
    *   **J (Dictionary)**: Collection of standard value definitions.
    *   **K (Corpus)**: Example sentences from real reports.
    *   **L (Rules)**: `Raw Text -> Code` mapping logic.
    *   **M (Synonyms)**: `Standard Term: Variant` synonym database.

### 1.2 Value Types
*   **Unique Value**: Must select **one** code from the J column dictionary.
*   **Multi-Value**: Can select **multiple** codes from the J column dictionary.
*   **Numeric Value**: Extract specific numbers (usually with units).
*   **Text**: Extract raw text description.
*   **Attribute Family**: This is a container node, **do not fill directly**, but fill its L2 or L3 child nodes.

---

## 2. Extraction Strategy

It is recommended to use a **"Hierarchical Retrieval + Semantic Mapping"** Two-Stage strategy.

### Stage 1: Entity Recognition & Context Localization
*   **Input**: The entire report text.
*   **Task**: Identify which specific artifact individuals (Objects) are described in the report.
*   **Output**: List of artifacts and their corresponding text paragraphs (Context Snippet).

### Stage 2: Attribute Extraction (Per Artifact)
*   **Input**: Artifact text paragraph + Extraction Template (Prompt Context).
*   **Principles**:
    1.  **Finest Granularity First**: If the template has `JCF01 Pendant` and `JCT0101 Jade Huang`, and the text explicitly mentions "Jade Huang", **only fill** `JCT0101`, and the system can automatically infer it belongs to `JCF01`.
    2.  **Follow Column L Rules**: Use `Term -> Code` rules from Column L as Few-shot examples for the LLM.
    3.  **Handle Multi-Values**: For "Function" or "Condition", if the original text involves multiple items, output as a list (e.g., `['FT101', 'FT104']`).

---

## 3. Prompt Design Demonstration

Recommended Prompt structure for LLM:

```markdown
# Role
You are a senior archaeological data expert.

# Task
Extract structured data from the given [Archaeological Report Fragment] and fill in the [Target Fields].

# Context
Report Fragment: "...The vessel is fine gray pottery, with a flared mouth and constricted neck, diameter 15cm, mainly used for cooking..."

# Target Fields Definition (From CSV)
1. ClayFabricType:
   - Dictionary: PS1: Fine clay ware; PS2: Sand-tempered...
   - Rules: Fine clay->PS1; Sand-tempered->PS2
2. Rim direction:
   - Dictionary: P1A301: Flared; P1A304: Everted...
   - Rules: Everted->P1A304
3. Neck Shape:
   - Dictionary: P2F101: Constricted...
   - Rules: Constricted->P2F101

# Output Requirement
Please output in JSON format, Key is the Field ID, Value is the extracted **Code**. If a numeric value is extracted, output the number directly.

# Your Output
{
  "ClayFabricType": "PS1",
  "P1F3": "P1A304",
  "P2F1": "P2F101",
  "MT201": 15
}
```

---

## 4. Post-Processing & Normalization

Since LLMs occasionally output Chinese names instead of codes, it is recommended to write a **normalization script**:

1.  **Load Mapping Table**: Read Columns `L` and `M` of the CSV to build a `Term -> Code` lookup table.
2.  **Clean Output**: Iterate through the JSON returned by the LLM.
    *   If Value is a code (e.g., `PS1`), keep it.
    *   If Value is Chinese (e.g., `Fine clay`), lookup table to convert to `PS1`.
    *   If Value is a synonym (e.g., `Reddish-brown pottery`), use Column M to find the standard term `Red pottery`, then convert to `BC1`.

## 5. Common Issue Handling

*   **Parent-Child Node Conflict**: If the LLM outputs values for both a parent node (e.g., `Attribute Family`) and a child node, **keep the child node and discard the parent node value**.
*   **Unit Conversion**: The default length unit in the template is `mm` or `cm`. It is recommended to unify the request for `cm` or `mm` in the Prompt, or perform regex extraction and conversion in post-processing.
*   **Unknown Values**: If not mentioned in the original text, output `null` or ignore the field, do not force fill "Unknown". Only fill the `Unknown` code if the text explicitly states "details unknown".
