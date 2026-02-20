# Excel 读取错误修复 (Excel Engine Fix)

## 问题描述
用户报告 `ValueError: Excel file format cannot be determined, you must specify an engine manually.`。
这是因为 Pandas 在读取 `.xlsx` 文件时，未能自动选择正确的引擎（openpyxl）。

## 修复方案

1.  **显式指定引擎**：
    修改 `src/template_analyzer.py`，在 `pd.read_excel` 中添加 `engine='openpyxl'` 参数。
    ```python
    self.df = pd.read_excel(template_path, engine='openpyxl')
    ```

2.  **过滤临时文件**：
    修改 `gui/app_v3.py`，在列出模板文件时，自动排除以 `~$` 开头的 Excel 临时锁文件，避免误选导致读取失败。

## 验证
重启 GUI 后，选择模板并运行抽取，不再报错。

---

**请重启 GUI 并重新尝试抽取。** 🚀

