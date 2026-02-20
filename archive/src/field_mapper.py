"""
字段映射器
将LLM返回的中文字段名映射到数据库的英文字段名
"""

from typing import Dict
from src.template_analyzer import TemplateAnalyzer


class FieldMapper:
    """
    字段映射器
    负责将LLM返回的中文字段映射到数据库英文字段
    """
    
    def __init__(self, template_path: str):
        """
        初始化字段映射器
        
        Args:
            template_path: 模板文件路径
        """
        self.template_analyzer = TemplateAnalyzer(template_path)
        # get_chinese_to_english_mapping 返回的是 {db_field: chinese_name} (英文->中文)
        en_to_cn = self.template_analyzer.get_chinese_to_english_mapping()
        # 反转为 {chinese_name: db_field} (中文->英文)，用于将LLM返回的中文字段映射为数据库字段
        self.cn_to_en = {v: k for k, v in en_to_cn.items() if v}
    
    def map_artifact_fields(self, artifact: Dict) -> Dict:
        """
        将文物数据的中文字段名映射为英文字段名
        
        Args:
            artifact: 包含中文字段名的文物数据
        
        Returns:
            包含英文字段名的文物数据
        """
        mapped = {}
        
        for cn_field, value in artifact.items():
            # 查找对应的英文字段名
            en_field = self.cn_to_en.get(cn_field, cn_field)
            mapped[en_field] = value
        
        return mapped
    
    def map_artifacts_batch(self, artifacts: list) -> list:
        """
        批量映射文物数据
        
        Args:
            artifacts: 文物数据列表
        
        Returns:
            映射后的文物数据列表
        """
        return [self.map_artifact_fields(art) for art in artifacts]


# 示例用法
if __name__ == "__main__":
    # 测试
    mapper = FieldMapper("抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx")
    
    test_artifact = {
        '陶土种类': '夹砂陶',
        '陶土纯洁程度 ': '较纯',
        '基本器型': '罐',
        '人工物品编号': 'M12:1'
    }
    
    mapped = mapper.map_artifact_fields(test_artifact)
    print("映射前:", test_artifact)
    print("映射后:", mapped)

