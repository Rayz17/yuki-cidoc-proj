"""
一个用于加载和处理考古报告数据结构模板的处理器。
"""

import pandas as pd
import os


class ReportProcessor:
    """
    用于处理考古报告和数据结构模板的核心类。
    """

    def __init__(self):
        self.template_data = []

    def load_template(self, template_path: str) -> list:
        """
        从指定的 .xlsx 文件中加载数据结构模板。

        Args:
            template_path (str): .xlsx 模板文件的路径。

        Returns:
            list: 包含模板中每一行数据的字典列表。
        """
        try:
            if not os.path.exists(template_path):
                raise FileNotFoundError(f"模板文件不存在: {template_path}")
            
            # 使用pandas读取Excel文件
            df = pd.read_excel(template_path)
            
            # 将DataFrame转换为字典列表
            # 使用orient='records'将每行转换为字典
            template_data = df.to_dict('records')
            
            # 清理数据：将NaN值转换为None，便于后续处理
            for item in template_data:
                for key, value in item.items():
                    if pd.isna(value):
                        item[key] = None
            
            print(f"✅ 已从 {template_path} 加载模板数据，共 {len(template_data)} 行。")
            return template_data

        except Exception as e:
            print(f"❌ 加载模板文件时出错 {template_path}: {e}")
            return []
