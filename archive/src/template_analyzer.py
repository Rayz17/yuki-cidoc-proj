"""
模板分析器：解析Excel数据结构模板，提取字段定义和元数据
"""

import pandas as pd
import re
from typing import Dict, List, Tuple


class TemplateAnalyzer:
    """
    分析数据结构模板，提取文化特征单元字段定义
    """
    
    def __init__(self, template_path: str):
        """
        初始化模板分析器
        
        Args:
            template_path: Excel模板文件路径
        """
        self.template_path = template_path
        try:
            self.df = pd.read_excel(template_path, engine='openpyxl')
        except Exception as e:
            raise ValueError(f"无法读取Excel文件 '{template_path}': {str(e)}。请确保安装了openpyxl库。")
        
        # 标准化列名（去除换行符）
        self.df.columns = [col.replace('\n', '') for col in self.df.columns]
        
        # 识别关键列名
        self._identify_key_columns()
    
    def _identify_key_columns(self):
        """识别模板中的关键列 (增强模糊匹配)"""
        columns = self.df.columns.tolist()
        
        # 辅助函数：模糊查找列名
        def find_col(keywords):
            if isinstance(keywords, str):
                keywords = [keywords]
            for col in columns:
                # 去除列名中的括号、空格等干扰字符进行比较，并转小写
                # 但保留原始col用于返回
                clean_col = re.sub(r'[（(].*?[)）]|\s', '', str(col)).lower()
                for kw in keywords:
                    if kw.lower() in clean_col:
                        return col
            return None

        # 查找文化特征单元列
        self.feature_column = find_col(['文化特征单元', '特征单元', '属性名', '字段名', '抽取属性'])
        
        if not self.feature_column:
            # 如果找不到，尝试使用包含"特征"的列
            for col in columns:
                if '特征' in str(col):
                    self.feature_column = col
                    break
            
            if not self.feature_column:
                raise ValueError(f"模板中未找到'文化特征单元'列。可用列: {columns}")
        
        # 其他关键列
        self.type_column = find_col(['文物类型', '适用对象'])
        self.description_column = find_col(['说明', '备注', '定义', 'description'])
        self.entity_column = find_col(['核心实体', 'entity'])
        self.property_column = find_col(['关系', 'property', 'predicate'])
        self.class_column = find_col(['中间类', 'class', 'target'])
    
    def get_artifact_types(self) -> List[str]:
        """
        获取模板中定义的文物类型列表
        
        Returns:
            文物类型列表，如 ['陶器', '玉器', '石器']
        """
        if not self.type_column:
            return ['文物']  # 默认值
        
        types = self.df[self.type_column].dropna().unique().tolist()
        # 过滤掉NaN和空字符串
        types = [t for t in types if str(t).strip() and str(t) != 'nan']
        return types if types else ['文物']
    
    def get_feature_fields(self) -> List[str]:
        """
        获取所有文化特征单元字段
        
        Returns:
            字段名列表，如 ['材料种类', '材料纯度', '硬度', ...]
        """
        fields = self.df[self.feature_column].dropna().tolist()
        # 过滤空值和NaN
        fields = [f for f in fields if str(f).strip() and str(f) != 'nan']
        return fields
    
    def get_field_metadata(self) -> Dict[str, Dict]:
        """
        获取字段元数据（描述、实体类型、关系等）
        
        Returns:
            字段元数据字典，格式:
            {
                '材料种类': {
                    'description': '识别构成文物材料的基本类型',
                    'entity_type': 'E22',
                    'property': 'P45 consists of',
                    'class': 'E57 Material'
                },
                ...
            }
        """
        metadata = {}
        
        for _, row in self.df.iterrows():
            field_name = row[self.feature_column]
            
            if pd.notna(field_name) and str(field_name).strip():
                field_name = str(field_name).strip()
                
                metadata[field_name] = {
                    'description': str(row.get(self.description_column, '')) if self.description_column else '',
                    'entity_type': str(row.get(self.entity_column, '')) if self.entity_column else '',
                    'property': str(row.get(self.property_column, '')) if self.property_column else '',
                    'class': str(row.get(self.class_column, '')) if self.class_column else ''
                }
                
                # 清理NaN值
                for key in metadata[field_name]:
                    if metadata[field_name][key] == 'nan':
                        metadata[field_name][key] = ''
        
        return metadata
    
    def generate_db_schema(self) -> Dict[str, str]:
        """
        生成数据库表结构定义
        
        Returns:
            字段名到SQL类型的映射，格式:
            {
                'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
                'artifact_code': 'TEXT UNIQUE',
                'material_type': 'TEXT',
                ...
            }
        """
        schema = {
            # 基础字段
            'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
            'artifact_code': 'TEXT UNIQUE',
            'artifact_type': 'TEXT',
            'subtype': 'TEXT',
            'found_in_tomb': 'TEXT',
            'extraction_confidence': 'REAL',
            'source_text_blocks': 'TEXT',  # JSON格式存储来源文本块ID
            'created_at': 'TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
        }
        
        # 添加文化特征单元字段
        fields = self.get_feature_fields()
        for field in fields:
            db_field_name = self.to_db_field_name(field)
            sql_type = self._infer_field_type(field)
            schema[db_field_name] = sql_type
        
        return schema
    
    def to_db_field_name(self, chinese_name: str) -> str:
        """
        将中文字段名转换为数据库字段名
        
        Args:
            chinese_name: 中文字段名，如 '材料种类'
        
        Returns:
            数据库字段名，如 'material_type'
        """
        # 预定义映射表 (Source of Truth: schema_v3.sql)
        mapping = {
            # ================== 陶器 (Pottery) ==================
            '陶土种类': 'clay_type',
            '陶土纯洁程度': 'clay_purity',
            '陶土纯洁程度 ': 'clay_purity',
            '陶土细腻程度': 'clay_fineness',
            '陶土细腻程度 ': 'clay_fineness',
            '掺杂物': 'mixed_materials',
            '硬度': 'hardness',
            '颜色': 'color',
            '表面处理': 'surface_treatment',
            '基本器型': 'basic_shape',
            '器型部位特征': 'shape_features',
            '器物组合': 'vessel_combination',
            '基本尺寸': 'dimensions',
            '器物功能': 'function',
            '成型工艺': 'forming_technique',
            '修整技术': 'finishing_technique',
            '装饰手法': 'decoration_method',
            '纹饰类型': 'decoration_type',
            '烧成温度': 'firing_temperature',
            '人工物品编号': 'artifact_code',
            '制作活动': 'production_activity',
            '制作者': 'maker',
            '制作年代': 'production_date',
            '制作地点': 'production_location',
            '原始出土地点': 'excavation_location',
            '发掘活动': 'excavation_activity',
            '出土墓葬': 'found_in_tomb',
            '保存状况': 'preservation_status',
            '完整程度': 'completeness',
            # 兼容旧/其他表述
            '高度': 'height', '器高': 'height', '通高': 'height',
            '口径': 'diameter', '直径': 'diameter', '腹径': 'diameter', '底径': 'diameter',
            '厚度': 'thickness', '壁厚': 'thickness', '器壁厚度': 'thickness',
            '量度信息': 'measurements', # [Update 1201]
            
            # 出土位置细分
            '所在墓地': 'location_site',
            '所在遗址': 'location_site',
            '墓葬编号': 'found_in_tomb',
            '层位': 'location_layer',
            '层位信息': 'location_layer',
            '其他单位': 'location_unit',
            '灰坑编号': 'location_unit',
            # [Update 1201] 虚拟字段映射，用于反向查找
            '出土区域': 'ex_region',
            '出土单位': 'ex_unit',
            '出土层位': 'ex_layer',

            # ================== 玉器 (Jade) ==================
            '人工物品编号': 'artifact_code',
            '一级分类': 'category_level1',
            '二级分类': 'category_level2',
            '三级分类': 'category_level3',
            '器型单元': 'shape_unit',
            '形状描述': 'shape_description', # 假设
            '整体形态描述': 'overall_description', # [New 1201]
            '纹饰单元': 'decoration_unit',
            '纹饰单元(按图案题材分类)': 'decoration_unit',
            '纹饰主题': 'decoration_theme',
            '纹饰描述': 'decoration_description',
            '工艺特征单元': 'craft_unit',
            '工艺特征单元(按制作痕迹分类)': 'craft_unit',
            '切割工艺': 'cutting_technique',
            '钻孔工艺': 'drilling_technique',
            '雕刻工艺': 'carving_technique',
            '装饰工艺': 'decoration_craft',
            '材质单元': 'jade_type',
            '玉料类型': 'jade_type',
            '玉料质地': 'jade_quality',
            '玉料颜色': 'jade_color',
            '透明度': 'transparency',
            '沁色单元': 'surface_condition', 
            '量度信息': 'measurements', # [Update 1201]
            '尺寸': 'dimensions',
            '长度': 'length', '长': 'length', '通长': 'length',
            '宽度': 'width', '宽': 'width',
            '厚度': 'thickness', '厚': 'thickness',
            '孔径': 'hole_diameter',
            '重量': 'weight',
            '器物功能': 'function',
            '使用方式': 'usage',
            '制作工艺': 'production_technique',
            '制作年代': 'production_period', # 玉器表是 production_period
            '原始出土地点': 'excavation_location',
            '出土墓葬': 'found_in_tomb',
            '保存状况': 'preservation_status',
            '完整程度': 'completeness',
            '表面状况': 'surface_condition',
            # [Update 1201] 虚拟字段映射
            '出土区域': 'ex_region',
            '出土单位': 'ex_unit',
            '出土层位': 'ex_layer',

            # ================== 遗址 (Sites) ==================
            '遗址编号': 'site_code',
            '遗址名称': 'site_name',
            '遗址别名': 'site_alias',
            '遗址类型': 'site_type',
            '地理位置': 'current_location',
            '现存地点': 'current_location',
            '遗址位置': 'current_location',
            '遗址当前位置': 'current_location',
            '所在地': 'current_location',
            '地理坐标': 'geographic_coordinates',
            '位置地理数据': 'geographic_coordinates',
            '遗址空间数据': 'spatial_data', # [New 1201]
            '海拔': 'elevation',
            '遗址面积': 'total_area',
            '总面积': 'total_area',
            '发掘面积': 'excavated_area',
            '文化属性': 'culture_name',
            '所属文化': 'culture_name',
            '所属年代': 'absolute_dating',
            '绝对年代': 'absolute_dating',
            '保护级别': 'protection_level',
            '保存状况': 'preservation_status',
            '自然环境': 'description', # 映射到 description 兜底
            '遗址描述': 'description',
            # 遗址结构相关 (Mapped to site_structures table logic in workflow, but here for safety)
            '遗址内子区域': 'site_sub_zone',
            '子区域编号或名称': 'sub_zone_name',
            '子区域位置描述': 'sub_zone_location',
            '子区域内具体单位': 'sub_zone_unit',
            '所属子区域': 'parent_sub_zone',

            # ================== 时期 (Periods) ==================
            '时期编号': 'period_code',
            '时期名称': 'period_name',
            '时期/期别': 'period_name', # [New 1201]
            '时期别名': 'period_alias',
            '起始时间': 'time_span_start',
            '结束时间': 'time_span_end',
            '绝对年代': 'absolute_dating',
            '相对年代': 'relative_dating',
            '发展阶段': 'development_stage',
            '阶段序列': 'phase_sequence',
            '时期顺序': 'phase_sequence', # [New 1201]
            '时期特征': 'characteristics',
            '代表性文物': 'representative_artifacts',
            '历史背景朝代': 'historical_era', # [New 1201]
            '细分时期划分': 'sub_period', # [New 1201]
            '物理地层归属': 'stratigraphic_layer', # [New 1201]
        }
        
        # 如果在映射表中，直接返回
        if chinese_name in mapping:
            return mapping[chinese_name]
        
        # 否则，进行自动转换
        # 1. 转拼音或使用简化规则
        # 这里使用简化规则：去除特殊字符，转小写，用下划线连接
        field_name = re.sub(r'[^\w\s]', '', chinese_name)
        field_name = field_name.strip().lower().replace(' ', '_')
        
        # 如果转换后为空或全是数字，使用原始名称的哈希
        if not field_name or field_name.isdigit():
            field_name = f"field_{abs(hash(chinese_name)) % 10000}"
        
        return field_name
    
    def _infer_field_type(self, field_name: str) -> str:
        """
        根据字段名推断SQL数据类型
        
        Args:
            field_name: 字段名
        
        Returns:
            SQL类型，如 'TEXT', 'REAL', 'INTEGER'
        """
        # 数值型字段
        numeric_keywords = ['硬度', '温度', '重量', '容量', '数量', '比例']
        if any(kw in field_name for kw in numeric_keywords):
            return 'REAL'
        
        # 整数型字段
        integer_keywords = ['数目', '件数', '层位']
        if any(kw in field_name for kw in integer_keywords):
            return 'INTEGER'
        
        # 默认为文本型
        return 'TEXT'
    
    def get_chinese_to_english_mapping(self) -> Dict[str, str]:
        """
        获取数据库字段名(EN)到中文字段名(CN)的映射 (用于GUI显示)
        
        Returns:
            映射字典 { 'english_name': '中文名' }
        """
        mapping = {
            'id': 'ID',
            'artifact_code': '单品编码',
            'artifact_type': '文物类型',
            'subtype': '子类型',
            'found_in_tomb': '出土墓葬',
            'extraction_confidence': '抽取置信度',
            'source_text_blocks': '来源文本块',
            'created_at': '创建时间'
        }
        
        # 添加文化特征单元字段的映射
        fields = self.get_feature_fields()
        for field in fields:
            db_name = self.to_db_field_name(field)
            mapping[db_name] = field
        
        return mapping

    def get_cn_to_en_mapping(self) -> Dict[str, str]:
        """
        获取中文字段名(CN)到数据库字段名(EN)的映射 (用于Prompt生成)
        
        Returns:
            映射字典 { '中文名': 'english_name' }
        """
        mapping = {}
        fields = self.get_feature_fields()
        for field in fields:
            db_name = self.to_db_field_name(field)
            mapping[field] = db_name
        return mapping
    
    def validate_template(self) -> Tuple[bool, List[str]]:
        """
        验证模板格式是否正确
        
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        # 检查必需列
        if not self.feature_column:
            errors.append("缺少'文化特征单元'列")
        
        # 检查是否有有效字段
        fields = self.get_feature_fields()
        if len(fields) == 0:
            errors.append("未找到任何有效的文化特征单元字段")
        
        # 检查字段名重复
        if len(fields) != len(set(fields)):
            duplicates = [f for f in fields if fields.count(f) > 1]
            errors.append(f"字段名重复: {set(duplicates)}")
        
        return (len(errors) == 0, errors)
    
    def get_summary(self) -> Dict:
        """
        获取模板摘要信息
        
        Returns:
            摘要字典
        """
        return {
            'template_path': self.template_path,
            'artifact_types': self.get_artifact_types(),
            'total_fields': len(self.get_feature_fields()),
            'fields': self.get_feature_fields(),
            'is_valid': self.validate_template()[0]
        }

    def get_template_definitions(self, artifact_type: str = None) -> List[Dict]:
        """
        获取模板定义列表，用于存入 sys_template_mappings 表
        
        Args:
            artifact_type: 指定文物类型（如果模板中有多种类型，可以强制指定）
                           如果为None，则使用模板中定义的类型（通常取第一个或全部）
        
        Returns:
            List of dicts, compatible with db.register_template_mappings
        """
        definitions = []
        metadata = self.get_field_metadata()
        
        # 确定文物类型
        if not artifact_type:
            types = self.get_artifact_types()
            # 如果模板中定义了多种类型，通常我们认为这是一份通用模板
            # 或者需要调用者明确指定。这里简单起见，如果没指定，就用模板里的第一个
            # 在 Workflow 中应该明确传入 'pottery' 或 'jade'
            artifact_type = types[0] if types else 'unknown'
            
            # 映射 '陶器' -> 'pottery', '玉器' -> 'jade'
            type_map = {'陶器': 'pottery', '玉器': 'jade', '遗址': 'site', '时期': 'period'}
            artifact_type = type_map.get(artifact_type, artifact_type)

        for field_name, meta in metadata.items():
            def_item = {
                'artifact_type': artifact_type,
                'field_name_cn': field_name,
                'field_name_en': self.to_db_field_name(field_name),
                'description': meta.get('description', ''),
                'cidoc_entity': meta.get('entity_type', ''),
                'cidoc_property': meta.get('property', ''),
                'target_class': meta.get('class', '')
            }
            definitions.append(def_item)
            
        return definitions


# 示例用法
if __name__ == "__main__":
    analyzer = TemplateAnalyzer('templates/文物文化特征单元数据结构.xlsx')
    
    print("=" * 60)
    print("模板分析结果")
    print("=" * 60)
    
    print(f"\n文物类型: {analyzer.get_artifact_types()}")
    print(f"\n文化特征单元字段数量: {len(analyzer.get_feature_fields())}")
    print(f"\n字段列表:")
    for i, field in enumerate(analyzer.get_feature_fields(), 1):
        db_name = analyzer.to_db_field_name(field)
        print(f"  {i}. {field} -> {db_name}")
    
    print(f"\n数据库表结构:")
    schema = analyzer.generate_db_schema()
    for field_name, field_type in schema.items():
        print(f"  {field_name}: {field_type}")
    
    print(f"\n模板验证:")
    is_valid, errors = analyzer.validate_template()
    if is_valid:
        print("  ✅ 模板格式正确")
    else:
        print("  ❌ 模板格式错误:")
        for error in errors:
            print(f"    - {error}")

