"""
提示词生成器
根据模板动态生成LLM提示词
"""

import json
import os
from typing import Dict, List, Optional
from src.template_analyzer import TemplateAnalyzer


class PromptGenerator:
    """
    提示词生成器
    根据不同的主体类型和模板动态生成提示词
    """
    
    def __init__(self):
        """初始化提示词生成器"""
        pass
    
    def generate_prompt(self, 
                       entity_type: str,
                       template_path: str,
                       text_block: str,
                       context: Optional[Dict] = None) -> str:
        """
        生成提示词
        
        Args:
            entity_type: 实体类型 (site/period/pottery/jade)
            template_path: 模板文件路径
            text_block: 待抽取的文本块
            context: 上下文信息（如遗址名称、时期等）
        
        Returns:
            完整的提示词
        """
        # 加载并分析模板
        template_analyzer = TemplateAnalyzer(template_path)
        
        # 获取字段列表和映射
        feature_fields = template_analyzer.get_feature_fields()
        field_metadata = template_analyzer.get_field_metadata()
        cn_to_en = template_analyzer.get_cn_to_en_mapping() # Fix: Use correct mapping direction
        db_schema = template_analyzer.generate_db_schema()
        
        # 构建完整的字段信息
        fields = []
        for field_cn in feature_fields:
            field_en = cn_to_en.get(field_cn, field_cn)
            field_type = db_schema.get(field_en, 'TEXT')
            fields.append({
                'chinese_name': field_cn,
                'english_name': field_en,
                'data_type': field_type,
                'description': field_metadata.get(field_cn, {}).get('description', '')
            })
        
        template_info = {'fields': fields}
        
        if entity_type == 'site':
            return self._generate_site_prompt(template_info, text_block, context)
        elif entity_type == 'period':
            return self._generate_period_prompt(template_info, text_block, context)
        elif entity_type == 'pottery':
            return self._generate_pottery_prompt(template_info, text_block, context)
        elif entity_type == 'jade':
            return self._generate_jade_prompt(template_info, text_block, context)
        else:
            raise ValueError(f"不支持的实体类型: {entity_type}")
    
    def _generate_site_prompt(self, template_info: Dict, text_block: str, context: Dict) -> str:
        """生成遗址抽取提示词"""
        fields = template_info['fields']
        field_descriptions = self._format_field_list(fields)
        
        prompt = f"""# 考古遗址信息抽取任务

## 任务说明
你是一位专业的考古学家助手。请从给定的考古报告文本中，抽取遗址的基本信息、特征以及**内部结构（如分区、功能区、具体遗迹等）**。

## 抽取字段
1. **基本信息**（如果文本中没有相关信息，该字段可以为空）：
{field_descriptions}

2. **遗址结构 (structures)**:
请识别文本中提到的遗址内部结构单元（如"居住区"、"墓葬区"、"祭坛"、"I区"、"M1号墓地"等），并作为列表返回。
结构单元包括：
- 分区 (Zone/Region)
- 建筑基址 (Foundation)
- 墓地 (Cemetery)
- 祭祀台 (Altar)
- 其他重要功能区

## 输出格式
请以JSON格式输出，结构如下：
```json
{{
  "site_name": "遗址名称",
  "site_type": "遗址类型",
  ...其他基本字段,
  "structures": [
    {{
      "structure_name": "名称 (如 'I区', '瑶山祭坛')",
      "structure_type": "类型 (如 '分区', '祭坛', '墓地')",
      "parent_structure_name": "上级结构名称 (如果属于某个大区)",
      "description": "描述 (位置、功能等)"
    }},
    ...
  ]
}}
```

## 注意事项
1. 只抽取文本中明确提到的信息，不要推测
2. 数值类型的字段请提取具体数字
3. 遗址结构应该包含层级关系（如果文本提到了）
4. 保持专业术语的准确性

## 待抽取文本
{text_block}

## 请开始抽取
"""
        return prompt
    
    def _generate_period_prompt(self, template_info: Dict, text_block: str, context: Dict) -> str:
        """生成时期抽取提示词"""
        fields = template_info['fields']
        field_descriptions = self._format_field_list(fields)
        
        site_name = context.get('site_name', '该遗址') if context else '该遗址'
        
        prompt = f"""# 考古时期信息抽取任务

## 任务说明
你是一位专业的考古学家助手。请从给定的考古报告文本中，抽取{site_name}的时期划分和特征信息。

## 抽取字段
请抽取以下字段（如果文本中没有相关信息，该字段可以为空）：

{field_descriptions}

## 输出格式
请以JSON格式输出时期列表，每个时期是一个对象：
```json
[
  {{
    "period_name": "时期名称",
    "time_span_start": "起始时间",
    "time_span_end": "结束时间",
    ...其他字段
  }},
  ...
]
```

## 注意事项
1. 时期可能有多个，请全部识别
2. 注意时期的先后顺序和发展阶段
3. 提取代表性文物特征
4. 如果有绝对年代和相对年代，都要提取

## 待抽取文本
{text_block}

## 请开始抽取
"""
        return prompt
    
    def _generate_pottery_prompt(self, template_info: Dict, text_block: str, context: Dict) -> str:
        """生成陶器抽取提示词"""
        fields = template_info['fields']
        field_descriptions = self._format_field_list(fields)
        
        # 提取上下文信息
        site_name = context.get('site_name', '') if context else ''
        period_name = context.get('period_name', '') if context else ''
        tomb_name = context.get('tomb_name', '') if context else ''
        
        context_info = ""
        if site_name:
            context_info += f"- 遗址: {site_name}\n"
        if period_name:
            context_info += f"- 时期: {period_name}\n"
        if tomb_name:
            context_info += f"- 墓葬: {tomb_name}\n"
        
        prompt = f"""# 陶器文物信息抽取任务

## 任务说明
你是一位专业的考古学家助手。请从给定的考古报告文本中，识别并抽取所有陶器文物的详细信息。

## 上下文信息
{context_info if context_info else "（无）"}

## 抽取字段
请抽取以下字段。**重要：即使文本中没有提到某个字段，也必须在返回的JSON中包含该字段的Key，并将Value设为null，严禁省略Key。**

{field_descriptions}

## 输出格式
请以JSON格式输出陶器列表，每个陶器是一个对象：
```json
[
  {{
    "artifact_code": "人工物品编号（如M1:1）",
    "subtype": "基本器型 (如 '罐', '豆', '壶')",
    
    "clay_type": "陶土种类 (如 '夹砂红陶', '泥质灰陶')",
    "clay_purity": "陶土纯洁程度",
    "clay_fineness": "陶土细腻程度",
    "mixed_materials": "掺杂物",
    
    "color": "颜色 (通常包含在陶土或外观描述中)",
    "hardness": "硬度",
    "firing_temperature": "烧成温度",
    
    "shape_features": "器型部位特征 (详细描述，如 '卷沿', '鼓腹')",
    "vessel_combination": "器物组合",
    
    "dimensions": "基本尺寸 (原文描述)",
    "height": 高度数值 (衍生自基本尺寸, cm),
    "diameter": 口径/直径数值 (衍生自基本尺寸, cm),
    "thickness": 壁厚数值 (衍生自基本尺寸, cm),
    
    "function": "器物功能",
    
    "forming_technique": "成型工艺",
    "finishing_technique": "修整技术 (如 '磨光', '刮削')",
    "surface_treatment": "表面处理 (衍生自修整技术)",
    
    "decoration_method": "装饰手法 (如 '刻划', '彩绘')",
    "decoration_type": "纹饰类型 (如 '绳纹', '几何纹')",
    
    "production_activity": "制作活动",
    "maker": "制作者",
    "production_date": "制作年代",
    "production_location": "制作地点",
    
    "excavation_location": "原始出土地点 (原文完整描述)",
    "ex_region": "出土区域/墓地 (如 '文家山墓地')",
    "ex_unit": "出土单位 (如 'M7', '七号墓')",
    "ex_layer": "出土层位 (如 '②层')",
    "found_in_tomb": "墓葬编号 (规范化的M号，如 'M7')",
    "location_unit": "其他遗迹单位 (如 'H1'灰坑)",
    
    "image_references": ["图1", "图版二:3"] (提取文中提到的关联图片编号),
    ...（必须包含上述“抽取字段”列表中的所有Key）
  }},
  ...
]
```

## 注意事项
1. **结构完整性**: 返回的JSON对象必须包含模版定义的所有字段Key，缺失值设为null。
2. 每个陶器都要有唯一的artifact_code（文物编号）。
3. **尺寸提取**: 必须将尺寸描述拆分为具体数值。例如"高15cm" -> dimensions="高15cm", height=15。
4. **墓葬编号规范化**: 如果文中提到"六号墓"或"M6"，请统一在 output 中使用 "M6" 格式。
5. **图片引用提取**: 如果文中提到了关联图片，请将其提取到 `image_references` 列表中。
6. **语义理解**: 字段名称可能与文本描述不完全一致。请根据上下文理解含义。例如，“物件开口处直径”应提取为“口径”。
7. **位置拆解**: 必须将“原始出土地点”拆解为 region (墓地/区域), unit (单位/墓/坑), layer (层位)。
8. **排除非陶器**: 本任务**只抽取陶器**（Pottery/Ceramic）。严禁抽取玉器（Jade）、石器（Stone）、骨器、铜器等其他质地的文物。即便它们出现在同一墓葬中，也请忽略。

## 待抽取文本
{text_block}

## 请开始抽取
"""
        return prompt
    
    def _generate_jade_prompt(self, template_info: Dict, text_block: str, context: Dict) -> str:
        """生成玉器抽取提示词"""
        fields = template_info['fields']
        field_descriptions = self._format_field_list(fields)
        
        # 提取上下文信息
        site_name = context.get('site_name', '') if context else ''
        period_name = context.get('period_name', '') if context else ''
        tomb_name = context.get('tomb_name', '') if context else ''
        
        context_info = ""
        if site_name:
            context_info += f"- 遗址: {site_name}\n"
        if period_name:
            context_info += f"- 时期: {period_name}\n"
        if tomb_name:
            context_info += f"- 墓葬: {tomb_name}\n"
        
        prompt = f"""# 玉器文物信息抽取任务

## 任务说明
你是一位专业的考古学家助手。请从给定的考古报告文本中，识别并抽取所有玉器文物的详细信息。

## 上下文信息
{context_info if context_info else "（无）"}

## 抽取字段
请抽取以下字段。**重要：必须严格对应模版定义的“文化特征单元”。部分字段需要进一步细分提取衍生信息，请在JSON中一并返回。**

{field_descriptions}

## 输出格式
请以JSON格式输出玉器列表，每个玉器是一个对象：
```json
[
  {{
    "artifact_code": "人工物品编号（如M1:1）",
    "category_level1": "一级分类",
    "category_level2": "二级分类",
    "category_level3": "三级分类",
    
    "jade_type": "材质单元 (如 '透闪石软玉')",
    "jade_color": "颜色 (从材质单元中衍生/分离，如 '黄')",
    "jade_quality": "质地 (从材质单元中衍生，如 '细腻')",
    
    "dimensions": "量度信息 (原文描述)",
    "measurements": "量度信息 (详细的测量数据描述)",
    "length": 长度数值 (衍生自量度信息, cm),
    "width": 宽度数值 (衍生自量度信息, cm),
    "thickness": 厚度数值 (衍生自量度信息, cm),
    "height": 高度数值 (衍生自量度信息, cm),
    "diameter": 直径数值 (衍生自量度信息, cm),
    "hole_diameter": 孔径数值 (衍生自量度信息, cm),
    "weight": 重量数值 (衍生自量度信息, g),
    
    "craft_unit": "工艺特征单元 (原文描述)",
    "cutting_technique": "切割工艺 (衍生自工艺特征)",
    "drilling_technique": "钻孔工艺 (衍生自工艺特征)",
    "carving_technique": "雕刻工艺 (衍生自工艺特征)",
    "decoration_craft": "装饰工艺 (衍生自工艺特征)",
    
    "decoration_unit": "纹饰单元 (原文描述)",
    "decoration_theme": "纹饰主题 (衍生自纹饰单元)",
    
    "function": "器物功能",
    "usage": "使用方式 (衍生自功能)",
    
    "excavation_location": "原始出土地点 (原文完整描述)",
    "ex_region": "出土区域/墓地 (如 '文家山墓地')",
    "ex_unit": "出土单位 (如 'M7', '七号墓')",
    "ex_layer": "出土层位 (如 '②层')",
    "found_in_tomb": "墓葬编号 (规范化的M号，如 'M7')",
    "location_unit": "其他遗迹单位 (如 'H1'灰坑)",
    
    "image_references": ["图1", "图版二:3"] (提取文中提到的关联图片编号),
    ...（包含列表中的其他所有字段）
  }},
  ...
]
```

## 注意事项
1. **结构完整性**: 返回的JSON对象必须包含模版定义的所有字段Key。
2. **主从关系**: 请注意区分“主字段”（如工艺特征单元）和“衍生字段”（如切割工艺）。主字段存储概括性描述，衍生字段存储细分类型。
3. **尺寸提取**: `dimensions` 字段存储完整描述，同时必须提取 `length`, `width` 等数值到对应衍生字段。
4. **墓葬编号规范化**: 统一使用 "M+数字" 格式（如 M12）。
5. **语义理解**: 字段名称可能与文本描述不完全一致。请根据上下文理解含义。
6. **位置拆解**: 必须将“原始出土地点”拆解为 region (墓地/区域), unit (单位/墓/坑), layer (层位)。
7. **排除非玉器**: 本任务**只抽取玉器**（Jade）。严禁抽取陶器（Pottery）、石器（Stone）、骨器、铜器等其他质地的文物。

## 待抽取文本
{text_block}

## 请开始抽取
"""
        return prompt
    
    def _format_field_list(self, fields: List[Dict]) -> str:
        """
        格式化字段列表为提示词
        
        Args:
            fields: 字段列表
        
        Returns:
            格式化的字段描述
        """
        lines = []
        for i, field in enumerate(fields, 1):
            chinese_name = field['chinese_name']
            english_name = field['english_name']
            data_type = field['data_type']
            description = field.get('description', '')
            
            # 数据类型说明
            type_desc = {
                'TEXT': '文本',
                'REAL': '数值',
                'INTEGER': '整数',
                'BOOLEAN': '是/否'
            }.get(data_type, '文本')
            
            line = f"{i}. **{chinese_name}** (`{english_name}`) - {type_desc}类型"
            if description and str(description).lower() != 'nan':
                line += f" (说明: {description})"
            
            lines.append(line)
        
        return '\n'.join(lines)
    
    def generate_batch_prompt(self,
                             entity_type: str,
                             template_path: str,
                             text_blocks: List[str],
                             context: Optional[Dict] = None) -> List[str]:
        """
        批量生成提示词
        
        Args:
            entity_type: 实体类型
            template_path: 模板路径
            text_blocks: 文本块列表
            context: 上下文信息
        
        Returns:
            提示词列表
        """
        prompts = []
        for text_block in text_blocks:
            prompt = self.generate_prompt(entity_type, template_path, text_block, context)
            prompts.append(prompt)
        return prompts
    
    def generate_merge_prompt(self,
                             entity_type: str,
                             partial_extractions: List[Dict]) -> str:
        """
        生成信息合并提示词
        用于合并多个文本块抽取的同一文物信息
        
        Args:
            entity_type: 实体类型
            partial_extractions: 部分抽取结果列表
        
        Returns:
            合并提示词
        """
        entity_name = {
            'pottery': '陶器',
            'jade': '玉器',
            'site': '遗址',
            'period': '时期'
        }.get(entity_type, '文物')
        
        extractions_json = json.dumps(partial_extractions, ensure_ascii=False, indent=2)
        
        prompt = f"""# {entity_name}信息合并任务

## 任务说明
以下是从不同文本块中抽取的{entity_name}信息，它们可能描述的是同一个{entity_name}，也可能是不同的{entity_name}。
请根据artifact_code（文物编号）识别相同的{entity_name}，并合并它们的信息。

## 合并规则
1. 如果artifact_code相同，则认为是同一个{entity_name}，需要合并
2. 合并时，优先保留更详细、更具体的信息
3. 如果某个字段在多个抽取结果中都有值但不一致，请保留最完整的那个
4. 数值类型的字段，如果有冲突，保留更精确的值
5. 如果artifact_code不同，则保持为独立的{entity_name}

## 待合并的抽取结果
```json
{extractions_json}
```

## 输出格式
请输出合并后的{entity_name}列表，格式与输入相同：
```json
[
  {{
    "artifact_code": "...",
    ...合并后的字段
  }},
  ...
]
```

## 请开始合并
"""
        return prompt


# 示例用法
if __name__ == "__main__":
    generator = PromptGenerator()
    
    # 测试陶器提示词生成
    print("=" * 60)
    print("测试陶器提示词生成")
    print("=" * 60)
    
    template_path = "抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx"
    test_text = """
    M12出土陶器3件。
    M12:1 陶罐，夹砂红陶，口径12厘米，底径8厘米，高15厘米。
    M12:2 陶钵，泥质灰陶，口径18厘米，高8厘米。
    M12:3 陶豆，泥质黑陶，高12厘米。
    """
    
    context = {
        'site_name': '瑶山遗址',
        'period_name': '良渚文化晚期',
        'tomb_name': 'M12'
    }
    
    if os.path.exists(template_path):
        prompt = generator.generate_prompt('pottery', template_path, test_text, context)
        print(prompt)
        print("\n✅ 陶器提示词生成成功")
    else:
        print(f"⚠️  模板文件不存在: {template_path}")
    
    # 测试合并提示词
    print("\n" + "=" * 60)
    print("测试合并提示词生成")
    print("=" * 60)
    
    partial_data = [
        {"artifact_code": "M12:1", "subtype": "罐", "color": "红"},
        {"artifact_code": "M12:1", "height": 15, "diameter": 12},
        {"artifact_code": "M12:2", "subtype": "钵", "color": "灰"}
    ]
    
    merge_prompt = generator.generate_merge_prompt('pottery', partial_data)
    print(merge_prompt[:500] + "...\n")
    print("✅ 合并提示词生成成功")
