"""
工作流编排器
协调整个抽取流程的执行
"""

import os
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional
import hashlib

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database_manager_v3 import DatabaseManagerV3
from src.image_manager import ImageManager
from src.template_analyzer import TemplateAnalyzer
from src.prompt_generator import PromptGenerator
from src.artifact_merger import ArtifactMerger
from src.image_linker import ImageLinker
from src.field_mapper import FieldMapper
from src.content_extractor import split_by_tomb
from src.automated_extractor import call_llm_api, extract_json_from_response, load_config


class ExtractionWorkflow:
    """
    抽取工作流编排器
    协调整个抽取流程
    """
    
    def __init__(self, db_path: str = 'database/artifacts_v3.db'):
        """
        初始化工作流
        
        Args:
            db_path: 数据库路径
        """
        self.db = DatabaseManagerV3(db_path)
        self.db.connect()
        
        self.prompt_generator = PromptGenerator()
        self.artifact_merger = ArtifactMerger()
        
        self.llm_config = load_config()
    
    def _check_cancellation(self, task_id: str):
        """检查任务是否被中止"""
        task = self.db.get_task(task_id)
        if task and task.get('status') == 'aborted':
            self.db.add_log(task_id, 'WARNING', '检测到中止信号，正在停止任务...')
            raise Exception("任务已由用户手动中止")

    def execute_full_extraction(self,
                               report_folder: str,
                               templates: Dict[str, str],
                               report_name: Optional[str] = None,
                               bot_id: Optional[str] = None,
                               api_key: Optional[str] = None,
                               task_id: Optional[str] = None) -> str:
        """
        执行完整的抽取流程
        
        Args:
            report_folder: 报告文件夹路径
            templates: 模板映射
            report_name: 报告名称
            bot_id: 指定使用的 Coze Bot ID
            api_key: 指定 Bot 对应的 API Token
            task_id: 任务ID (如果已创建任务)
        
        Returns:
            任务ID
        """
        # 如果提供了 bot_id/api_key，更新 llm_config
        if bot_id:
            self.llm_config['llm']['bot_id'] = bot_id
            print(f"🤖 使用指定的 Bot ID: {bot_id}")
        
        if api_key:
            self.llm_config['llm']['api_key'] = api_key
            # print(f"🔑 使用指定的 API Key: {api_key[:4]}...")

        # 1. 创建任务 (如果没有传入 task_id)
        if not task_id:
            task_id = self.create_task(report_folder, report_name)
            
        self.db.add_log(task_id, 'INFO', '开始抽取流程')
        
        try:
            # 更新任务状态为running
            self.db.update_task_status(task_id, 'running')
            self._check_cancellation(task_id)
            
            # --- V3.2 新增：注册模版映射 ---
            self.db.add_log(task_id, 'INFO', '注册模版映射...')
            for type_key, template_path in templates.items():
                self._check_cancellation(task_id)
                try:
                    analyzer = TemplateAnalyzer(template_path)
                    # 明确传入artifact_type, 避免模版不确定性
                    mappings = analyzer.get_template_definitions(type_key)
                    self.db.register_template_mappings(mappings)
                    self.db.add_log(task_id, 'INFO', f'已注册 {type_key} 模版映射')
                except Exception as e:
                    self.db.add_log(task_id, 'WARNING', f'{type_key} 模版注册失败: {str(e)}')
            # -----------------------------

            # 2. 索引图片
            self._check_cancellation(task_id)
            self.db.add_log(task_id, 'INFO', '索引图片...')
            image_stats = self._index_images(task_id, report_folder)
            self.db.add_log(task_id, 'INFO', f'图片索引完成: {image_stats["total"]}张')
            
            # 3. 抽取遗址信息
            # V3.3 Update: 尝试复用已存在的Site ID，实现增量更新
            self._check_cancellation(task_id)
            existing_site = self.db.get_site_by_report(report_folder)
            
            if 'site' in templates:
                self.db.add_log(task_id, 'INFO', '抽取遗址信息...')
                
                if existing_site:
                    # ... (existing logic for updating site by ID) ...
                    site_id = existing_site['id']
                    self.db.add_log(task_id, 'INFO', f'发现已有遗址记录 (ID: {site_id})，将执行更新模式')
                    new_site_id = self._extract_site(task_id, report_folder, templates['site'], existing_site_id=site_id)
                    site_id = new_site_id
                else:
                    # V3.4 Update: 跨报告合并逻辑
                    # 在创建新Site之前，先检查是否已经存在同名的Site
                    # 这需要先抽取Site信息，看看名字是啥，然后再决定是 Insert 还是 Update
                    
                    # 1. 预抽取信息 (不插入DB)
                    pre_site_data = self._extract_site_data_only(task_id, report_folder, templates['site'])
                    site_name = pre_site_data.get('site_name')
                    
                    found_site = None
                    if site_name:
                        # 2. 按名称查找现有遗址
                        found_site = self.db.get_site_by_name(site_name)
                        
                    if found_site:
                        site_id = found_site['id']
                        self.db.add_log(task_id, 'INFO', f'根据名称 "{site_name}" 匹配到已有遗址 (ID: {site_id})，合并数据')
                        
                        # 3. 执行更新
                        # 更新 task_id 关联 (可选，或者记录 log)
                        # 更新 Site 信息
                        self.db.update_site(site_id, pre_site_data)
                    else:
                        # 3. 插入新遗址
                        site_id = self.db.insert_site(pre_site_data)
                    
                    # 更新任务的site_id
                    self.db.conn.execute(
                        'UPDATE extraction_tasks SET site_id = ? WHERE task_id = ?',
                        (site_id, task_id)
                    )
                    self.db.conn.commit()
                    
                self.db.add_log(task_id, 'INFO', f'遗址信息处理完成: site_id={site_id}')
            else:
                # 没选遗址模版
                if existing_site:
                    site_id = existing_site['id']
                    self.db.add_log(task_id, 'INFO', f'复用已有遗址 ID: {site_id}')
                else:
                    # 尝试根据报告名猜测遗址名并查找 (简单逻辑)
                    report_name = os.path.basename(report_folder)
                    # 假设报告名包含遗址名
                    found_site = self.db.get_site_by_name(report_name) 
                    if found_site:
                        site_id = found_site['id']
                        self.db.add_log(task_id, 'INFO', f'根据报告名猜测匹配到遗址 ID: {site_id}')
                    else:
                        site_id = None
            
            # 4. 抽取时期信息
            period_count = 0
            if 'period' in templates and site_id:
                self._check_cancellation(task_id)
                self.db.add_log(task_id, 'INFO', '抽取时期信息...')
                period_count = self._extract_periods(task_id, site_id, report_folder, templates['period'])
                self.db.add_log(task_id, 'INFO', f'时期信息抽取完成: {period_count}个')
            
            # 5. 抽取陶器信息
            pottery_count = 0
            if 'pottery' in templates:
                self._check_cancellation(task_id)
                self.db.add_log(task_id, 'INFO', '抽取陶器信息...')
                pottery_count = self._extract_artifacts(
                    task_id, site_id, report_folder, templates['pottery'], 'pottery'
                )
                self.db.add_log(task_id, 'INFO', f'陶器信息抽取完成: {pottery_count}件')
            
            # 6. 抽取玉器信息
            jade_count = 0
            if 'jade' in templates:
                self._check_cancellation(task_id)
                self.db.add_log(task_id, 'INFO', '抽取玉器信息...')
                jade_count = self._extract_artifacts(
                    task_id, site_id, report_folder, templates['jade'], 'jade'
                )
                self.db.add_log(task_id, 'INFO', f'玉器信息抽取完成: {jade_count}件')
            
            # 7. 更新统计信息
            self.db.update_task_statistics(task_id, {
                'total_pottery': pottery_count,
                'total_jade': jade_count,
                'total_periods': period_count if 'period_count' in locals() else 0,
                'total_images': image_stats['total']
            })
            
            # 8. 完成任务
            self.db.update_task_status(task_id, 'completed')
            self.db.add_log(task_id, 'INFO', '抽取流程完成')
            
            return task_id
            
        except Exception as e:
            self.db.add_log(task_id, 'ERROR', f'抽取失败: {str(e)}')
            self.db.update_task_status(task_id, 'failed')
            # 记录详细错误信息
            import traceback
            error_detail = traceback.format_exc()
            self.db.add_log(task_id, 'ERROR', f'错误详情: {error_detail[:500]}')
            raise
    
    def create_task(self, report_folder: str, report_name: Optional[str] = None) -> str:
        """创建抽取任务"""
        import random
        # 添加随机后缀以支持并发任务在同一秒内创建
        random_suffix = f"{random.randint(1000, 9999)}"
        task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{random_suffix}"
        
        if not report_name:
            report_name = os.path.basename(report_folder)
        
        # 查找报告文件
        markdown_path = self._find_file(report_folder, 'full.md')
        layout_json_path = self._find_file(report_folder, 'layout.json')
        content_list_json_path = self._find_file(report_folder, '*_content_list.json')
        images_folder_path = os.path.join(report_folder, 'images')
        
        task_data = {
            'task_id': task_id,
            'report_name': report_name,
            'report_folder_path': report_folder,
            'markdown_path': markdown_path,
            'layout_json_path': layout_json_path,
            'content_list_json_path': content_list_json_path,
            'images_folder_path': images_folder_path if os.path.exists(images_folder_path) else None
        }
        
        self.db.create_task(task_data)
        return task_id
    
    def _find_file(self, folder: str, pattern: str) -> Optional[str]:
        """查找文件"""
        if '*' in pattern:
            # 通配符匹配
            import glob
            files = glob.glob(os.path.join(folder, pattern))
            return files[0] if files else None
        else:
            # 精确匹配
            file_path = os.path.join(folder, pattern)
            return file_path if os.path.exists(file_path) else None
    
    def _index_images(self, task_id: str, report_folder: str) -> Dict:
        """索引图片"""
        img_manager = ImageManager(report_folder)
        images_data = img_manager.index_all_images()
        
        # 插入数据库（使用INSERT OR IGNORE避免重复）
        for img_data in images_data:
            img_data['task_id'] = task_id
            try:
                self.db.insert_image(img_data)
            except Exception as e:
                # 如果图片已存在（违反UNIQUE约束），跳过
                if 'UNIQUE constraint failed' in str(e):
                    continue
                else:
                    raise
        
        return img_manager.get_statistics()
    
    def _expand_code_with_llm(self, code: str) -> List[str]:
        """
        使用LLM智能解析复杂的文物编号范围
        """
        try:
            # 构造专门的Prompt
            prompt = f"""
你是一个专业的考古数据处理助手。请将以下包含范围或列表的文物编号字符串，解析展开为标准的独立文物编号列表。

示例 1:
输入: "M7:63-1~3"
输出: ["M7:63-1", "M7:63-2", "M7:63-3"]

示例 2:
输入: "M7:1、2、5"
输出: ["M7:1", "M7:2", "M7:5"]

示例 3:
输入: "M7:63-1~63-3"
输出: ["M7:63-1", "M7:63-2", "M7:63-3"]

待处理输入: "{code}"

请直接返回JSON字符串列表，不要包含Markdown标记（如 ```json）或其他解释性文字。
"""
            # 调用LLM（使用较低的温度以获得确定的结果）
            config = self.llm_config.copy()
            if 'llm' in config:
                config['llm']['temperature'] = 0.1
            
            response = call_llm_api(prompt, config)
            result = extract_json_from_response(response)
            
            if isinstance(result, list):
                # 过滤非字符串项
                return [str(item) for item in result if item]
            return []
            
        except Exception as e:
            print(f"LLM expansion failed for {code}: {e}")
            return []

    def _expand_artifact_ranges(self, artifacts: List[Dict]) -> List[Dict]:
        """
        扩展包含范围的文物编号，采用 "规则优先 + LLM兜底" 的策略
        """
        import re
        expanded = []
        
        for artifact in artifacts:
            # V3.10 Fix: Handle artifact_code being None
            code = artifact.get('artifact_code')
            if code is None:
                code = ''
            else:
                code = str(code).strip()
                
            is_expanded = False
            
            # 1. 规则层：尝试处理标准的 '~' 范围
            if '~' in code:
                try:
                    parts = code.split('~')
                    if len(parts) == 2:
                        start_full = parts[0].strip()
                        end_full = parts[1].strip()
                        
                        # 解析起始编号
                        start_match = re.search(r'^(.*?)(\d+)$', start_full)
                        if start_match:
                            prefix = start_match.group(1)
                            start_num = int(start_match.group(2))
                            
                            # 解析结束编号
                            end_match = re.search(r'(\d+)$', end_full)
                            if end_match:
                                end_num = int(end_match.group(1))
                                
                                # 验证范围合理性
                                if start_num < end_num and (end_num - start_num) < 100:
                                    for i in range(start_num, end_num + 1):
                                        new_artifact = artifact.copy()
                                        new_artifact['artifact_code'] = f"{prefix}{i}"
                                        expanded.append(new_artifact)
                                    is_expanded = True
                except Exception:
                    pass # 规则解析失败，留给LLM处理
            
            # 2. 兜底层：如果规则未处理，且看起来像复杂列表（包含分隔符），则调用LLM
            # 检查常见分隔符：、 , 和 至
            if not is_expanded:
                complex_indicators = ['、', ',', '，', '和', '至', '&']
                # 如果包含上述符号，或者包含 ~ 但上面没处理成功
                if any(char in code for char in complex_indicators) or ('~' in code and not is_expanded):
                    
                    print(f"🔍 检测到复杂编号 '{code}'，正在调用LLM进行智能展开...")
                    expanded_codes = self._expand_code_with_llm(code)
                    
                    if expanded_codes:
                        print(f"   -> LLM展开结果: {expanded_codes}")
                        for new_code in expanded_codes:
                            new_artifact = artifact.copy()
                            new_artifact['artifact_code'] = new_code
                            expanded.append(new_artifact)
                        is_expanded = True
            
            # 3. 如果都没处理，保留原样
            if not is_expanded:
                expanded.append(artifact)
            
        return expanded

    def _generate_triples(self, data: Dict, artifact_type: str, artifact_id: int, task_id: str):
        """生成并插入语义三元组"""
        try:
            # 1. 获取模版映射信息 (ID & Property)
            cursor = self.db.conn.cursor()
            # V3.6 Fix: 同时查询中文和英文字段名，以支持LLM返回任一种格式
            cursor.execute(
                'SELECT field_name_cn, field_name_en, id, cidoc_property FROM sys_template_mappings WHERE artifact_type = ?',
                (artifact_type,)
            )
            mappings = cursor.fetchall() # [(name_cn, name_en, id, prop), ...]
            
            import re
            def clean_string(s): return re.sub(r'\s+', '', str(s)).lower()
            
            # 构建查找表: clean_name -> (id, prop)
            map_lookup = {}
            for name_cn, name_en, mid, prop in mappings:
                if name_cn:
                    map_lookup[clean_string(name_cn)] = (mid, prop)
                if name_en:
                    map_lookup[clean_string(name_en)] = (mid, prop)
                
            triples = []
            for key, value in data.items():
                if not value: continue
                
                # 尝试匹配
                clean_key = clean_string(key)
                match = map_lookup.get(clean_key)
                
                if match:
                    mid, prop = match
                    if prop: # 只有定义了Property的字段才生成三元组
                        triples.append({
                            'artifact_type': artifact_type,
                            'artifact_id': artifact_id,
                            'mapping_id': mid,
                            'predicate': prop,
                            'object_value': str(value),
                            'confidence': data.get('extraction_confidence', 1.0)
                        })
                        
            if triples:
                self.db.insert_fact_triples(triples)
        except Exception as e:
            self.db.add_log(task_id, 'WARNING', f'生成三元组失败: {str(e)}')

    def _extract_site_data_only(self, task_id: str, report_folder: str, template_path: str) -> Dict:
        """
        仅抽取遗址数据，不插入数据库
        用于预检查遗址名称
        """
        # 读取报告文本
        markdown_path = os.path.join(report_folder, 'full.md')
        if not os.path.exists(markdown_path):
            raise FileNotFoundError(f"报告文件不存在: {markdown_path}")
        
        with open(markdown_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
        
        # 取前5000字
        site_text = full_text[:5000]
        
        # 生成提示词
        prompt = self.prompt_generator.generate_prompt(
            'site', template_path, site_text, {'report_name': task_id}
        )
        
        # 调用LLM
        response = call_llm_api(prompt, self.llm_config)
        site_data = extract_json_from_response(response)
        
        # 补充基础字段
        site_data['task_id'] = task_id
        site_data['source_text_blocks'] = json.dumps([0])
        site_data['extraction_confidence'] = 0.8
        
        # 保存原始数据到 raw_attributes
        system_fields = ['task_id', 'source_text_blocks', 'extraction_confidence']
        raw_dict = {k: v for k, v in site_data.items() if k not in system_fields}
        site_data['raw_attributes'] = json.dumps(raw_dict, ensure_ascii=False)
        
        # 确保 site_name
        if 'site_name' not in site_data or not site_data['site_name']:
            for k in ['遗址名称', '名称', 'Name', 'Site Name']:
                if site_data.get(k):
                    site_data['site_name'] = site_data[k]
                    break
            if 'site_name' not in site_data or not site_data['site_name']:
                # V3.3 Fix: 使用报告名称作为兜底
                task_info = self.db.get_task(task_id)
                report_name = task_info.get('report_name', 'Unknown Site') if task_info else 'Unknown Site'
                site_data['site_name'] = report_name
                # 只是预抽取，但为了后续insert_site不报错，必须赋值
                pass
                
        return site_data

    def _extract_site(self, task_id: str, report_folder: str, template_path: str, existing_site_id: int = None) -> int:
        """抽取遗址信息"""
        # 读取报告文本
        markdown_path = os.path.join(report_folder, 'full.md')
        if not os.path.exists(markdown_path):
            raise FileNotFoundError(f"报告文件不存在: {markdown_path}")
        
        with open(markdown_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
        
        # 取前5000字作为遗址信息（通常在报告开头）
        site_text = full_text[:5000]
        
        # 生成提示词
        prompt = self.prompt_generator.generate_prompt(
            'site', template_path, site_text, {'report_name': task_id}
        )
        
        # 调用LLM
        response = call_llm_api(prompt, self.llm_config)
        site_data = extract_json_from_response(response)
        
        # 插入数据库
        site_data['task_id'] = task_id
        site_data['source_text_blocks'] = json.dumps([0])  # 文本块索引
        site_data['extraction_confidence'] = 0.8
        
        # 保存原始数据到 raw_attributes (排除系统字段)
        # 这确保了即使某些字段因映射问题被过滤，原始数据仍然保留
        system_fields = ['task_id', 'source_text_blocks', 'extraction_confidence']
        raw_dict = {k: v for k, v in site_data.items() if k not in system_fields}
        site_data['raw_attributes'] = json.dumps(raw_dict, ensure_ascii=False)
        
        # V3.3 Fix: 确保 site_name 存在
        if 'site_name' not in site_data or not site_data['site_name']:
            # 尝试查找其他可能的键名
            for k in ['遗址名称', '名称', 'Name', 'Site Name']:
                if site_data.get(k):
                    site_data['site_name'] = site_data[k]
                    break
            
            # 如果还是没有，使用报告名称作为兜底
            if 'site_name' not in site_data or not site_data['site_name']:
                task_info = self.db.get_task(task_id)
                report_name = task_info.get('report_name', 'Unknown Site') if task_info else 'Unknown Site'
                site_data['site_name'] = report_name
                self.db.add_log(task_id, 'WARNING', f'未提取到遗址名称，使用报告名称 "{report_name}" 代替')
        
        print(f"DEBUG: site_name before insert: {site_data.get('site_name')}") # Debug print

        if existing_site_id:
            # 更新模式
            self.db.update_site(existing_site_id, site_data)
            site_id = existing_site_id
        else:
            site_id = self.db.insert_site(site_data)
        
        # V3.5: 生成并插入遗址的语义三元组
        self._generate_triples(site_data, 'site', site_id, task_id)

        # V3.9: 处理遗址结构 (Structures)
        structures = site_data.get('structures', [])
        if structures and isinstance(structures, list):
            self.db.add_log(task_id, 'INFO', f'发现 {len(structures)} 个遗址结构单元，正在处理...')
            
            # 第一轮：插入所有结构，建立名称映射
            structure_name_map = {} # name -> id
            
            for struct in structures:
                if not isinstance(struct, dict): continue
                struct_name = struct.get('structure_name')
                if not struct_name: continue
                
                # 准备数据
                struct_data = {
                    'site_id': site_id,
                    'structure_name': struct_name,
                    'structure_type': struct.get('structure_type'),
                    'description': struct.get('description'),
                    'source_text_blocks': json.dumps([0])
                }
                
                # 检查是否存在
                existing_struct = self.db.get_structure_by_name(site_id, struct_name)
                if existing_struct:
                    # 更新
                    struct_id = existing_struct['id']
                    self.db.update_structure(struct_id, struct_data)
                else:
                    # 插入
                    struct_id = self.db.insert_structure(struct_data)
                
                structure_name_map[struct_name] = struct_id
            
            # 第二轮：更新父子关系
            for struct in structures:
                struct_name = struct.get('structure_name')
                parent_name = struct.get('parent_structure_name')
                
                if struct_name and parent_name and struct_name in structure_name_map:
                    parent_id = structure_name_map.get(parent_name)
                    if parent_id:
                        struct_id = structure_name_map[struct_name]
                        # 更新 parent_id
                        self.db.conn.execute(
                            'UPDATE site_structures SET parent_id = ? WHERE id = ?',
                            (parent_id, struct_id)
                        )
            self.db.conn.commit()
            self.db.add_log(task_id, 'INFO', f'遗址结构处理完成')
        
        # 更新任务的site_id
        self.db.conn.execute(
            'UPDATE extraction_tasks SET site_id = ? WHERE task_id = ?',
            (site_id, task_id)
        )
        self.db.conn.commit()
        
        return site_id
    
    def _extract_periods(self, task_id: str, site_id: int, 
                        report_folder: str, template_path: str) -> int:
        """抽取时期信息"""
        # 读取报告文本
        markdown_path = os.path.join(report_folder, 'full.md')
        with open(markdown_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
        
        # 查找时期相关章节（通常在报告中部）
        period_text = full_text[5000:15000]  # 简化处理
        
        # 生成提示词
        site_info = self.db.get_site_by_task(task_id)
        context = {'site_name': site_info.get('site_name', '')} if site_info else {}
        
        prompt = self.prompt_generator.generate_prompt(
            'period', template_path, period_text, context
        )
        
        # 调用LLM
        response = call_llm_api(prompt, self.llm_config)
        periods_data = extract_json_from_response(response)
        
        # 确保是列表
        if isinstance(periods_data, dict):
            periods_data = [periods_data]
        
        # 插入数据库
        for period_data in periods_data:
            period_data['task_id'] = task_id
            period_data['site_id'] = site_id
            period_data['source_text_blocks'] = json.dumps([1])
            period_data['extraction_confidence'] = 0.8
            period_id = self.db.insert_period(period_data)
            
            # V3.5: 生成并插入时期的语义三元组
            if period_id:
                self._generate_triples(period_data, 'period', period_id, task_id)
        
        return len(periods_data)
    
    def _split_large_text(self, text: str, chunk_size: int = 2000, overlap: int = 200) -> List[str]:
        """
        将长文本智能切分为重叠的片段，优先在换行符处切分
        """
        if len(text) <= chunk_size:
            return [text]
            
        chunks = []
        start = 0
        
        while start < len(text):
            # 预设结束位置
            end = start + chunk_size
            
            # 如果超出总长度，就到最后
            if end >= len(text):
                chunks.append(text[start:])
                break
                
            # 在 chunk_size 范围内寻找最近的换行符，避免切断句子
            # 我们在 end 附近向前找换行符
            # 搜索范围: [end - overlap, end]
            search_start = max(start, end - overlap)
            last_newline = text.rfind('\n', search_start, end)
            
            if last_newline != -1:
                # 找到了换行符，在此处切分
                actual_end = last_newline + 1 # 包含换行符
            else:
                # 没找到换行符，尝试找句号
                last_period = text.rfind('。', search_start, end)
                if last_period != -1:
                    actual_end = last_period + 1
                else:
                    # 实在找不到分隔符，就硬切
                    actual_end = end
            
            chunks.append(text[start:actual_end])
            
            # 下一段的开始位置 = 当前结束位置 - 重叠量 (为了上下文连续性)
            # 如果是按换行符切的，其实可以不重叠，但为了保险起见，如果是硬切的需要重叠
            # 这里简单处理：直接从 actual_end 开始，不做额外重叠，
            # 因为 ArtifactMerger 会处理跨片段的实体，
            # 但为了防止一个实体描述正好被切断，我们还是稍微回退一点点，或者依赖ArtifactMerger
            # 考虑到我们的merger是基于 artifact_code 的，如果code被切断了就麻烦了。
            # 所以保留 overlap 是安全的。
            start = max(start + 1, actual_end - overlap) # 确保至少前进1个字符
            
        return chunks

    def _extract_artifacts(self, task_id: str, site_id: Optional[int],
                          report_folder: str, template_path: str,
                          artifact_type: str) -> int:
        """
        抽取文物信息
        
        Args:
            task_id: 任务ID
            site_id: 遗址ID
            report_folder: 报告文件夹
            template_path: 模板路径
            artifact_type: 文物类型 (pottery/jade)
        
        Returns:
            抽取的文物数量
        """
        # 读取报告文本
        markdown_path = os.path.join(report_folder, 'full.md')
        with open(markdown_path, 'r', encoding='utf-8') as f:
            full_text = f.read()
        
        # 按墓葬分块
        tomb_dict = split_by_tomb(full_text)
        
        if not tomb_dict:
            self.db.add_log(task_id, 'WARNING', f'未找到墓葬分块，使用整体文本')
            tomb_blocks = [('全文', full_text)]
        else:
            # 将字典转换为列表 [(tomb_name, tomb_text), ...]
            tomb_blocks = list(tomb_dict.items())
        
        self.db.add_log(task_id, 'INFO', f'文本分为{len(tomb_blocks)}个墓葬块')
        
        # 获取站点信息作为上下文
        site_info = self.db.get_site_by_task(task_id) if site_id else {}
        
        # 逐块抽取
        all_artifacts = []
        for i, tomb_block in enumerate(tomb_blocks):
            self._check_cancellation(task_id)
            tomb_name, tomb_text = tomb_block
            self.db.add_log(task_id, 'INFO', f'处理 {tomb_name} ({i+1}/{len(tomb_blocks)})')
            
            # V3.3: 智能切分长文本
            # 如果文本过长(>3000字符)，切分为片段分别抽取，防止LLM响应截断
            text_chunks = self._split_large_text(tomb_text, chunk_size=3000, overlap=300)
            
            if len(text_chunks) > 1:
                self.db.add_log(task_id, 'INFO', f'文本过长，已切分为 {len(text_chunks)} 个片段进行抽取')
            
            for chunk_idx, chunk_text in enumerate(text_chunks):
                self._check_cancellation(task_id)
                if len(text_chunks) > 1:
                    self.db.add_log(task_id, 'INFO', f'  -> 正在抽取片段 {chunk_idx+1}/{len(text_chunks)}...')
                
                # 生成提示词
                context = {
                    'site_name': site_info.get('site_name', '') if site_info else '',
                    'tomb_name': tomb_name
                }
                
                # 如果是切分片段，最好在prompt里提示一下（可选，目前prompt模板比较通用，可能不需要）
                prompt = self.prompt_generator.generate_prompt(
                    artifact_type, template_path, chunk_text, context
                )
                
                try:
                    # 调用LLM
                    response = call_llm_api(prompt, self.llm_config)
                    artifacts = extract_json_from_response(response)
                    
                    # 确保是列表
                    if isinstance(artifacts, dict):
                        artifacts = [artifacts]
                    
                    # 添加元数据
                    for artifact in artifacts:
                        artifact['task_id'] = task_id
                        artifact['site_id'] = site_id
                        # 记录源文本块索引：这里存的是 tomb_idx，不是 chunk_idx
                        artifact['source_text_blocks'] = json.dumps([i]) 
                        artifact['extraction_confidence'] = 0.8
                        artifact['found_in_tomb'] = tomb_name
                    
                    all_artifacts.extend(artifacts)
                    self.db.add_log(task_id, 'INFO', f'{tomb_name} (片段{chunk_idx+1}) 抽取到 {len(artifacts)} 件')
                    
                except Exception as e:
                    error_msg = f'{tomb_name} (片段{chunk_idx+1}) 抽取失败: {str(e)}'
                    self.db.add_log(task_id, 'ERROR', error_msg)
                    
                    # --- 补救机制：保存失败的原始响应 ---
                    if 'response' in locals() and response:
                        try:
                            log_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'logs', 'failed_responses')
                            os.makedirs(log_dir, exist_ok=True)
                            
                            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                            # 文件名包含 task_id 以便关联
                            filename = f"failed_{task_id}_{timestamp}_{i}_{chunk_idx}.txt"
                            filepath = os.path.join(log_dir, filename)
                            
                            with open(filepath, 'w', encoding='utf-8') as f:
                                f.write(f"Task ID: {task_id}\n")
                                f.write(f"Artifact Type: {artifact_type}\n")
                                f.write(f"Context: {tomb_name} (Chunk {chunk_idx+1})\n")
                                f.write(f"Error: {str(e)}\n")
                                f.write("-" * 50 + "\n")
                                f.write(response)
                                
                            self.db.add_log(task_id, 'WARNING', f'已保存失败的响应片段至: {filename}，可在任务管理中查看并恢复')
                        except Exception as save_err:
                            print(f"保存失败响应时出错: {save_err}")
                    # -----------------------------------
                    
                    continue
        
        
        # V3.3: 扩展编号范围 (如 M7:63-1~26)
        self.db.add_log(task_id, 'INFO', f'检查并扩展文物编号范围...')
        all_artifacts = self._expand_artifact_ranges(all_artifacts)

        # V3.5: 清洗墓葬名称 (Tomb Name Normalization)
        # 必须在合并前做，以便正确归类
        import re
        for artifact in all_artifacts:
            # 1. 尝试从 artifact_code 推断 (如 "M12:1" -> "M12")
            code = artifact.get('artifact_code')
            if code is None:
                code = ''
            else:
                code = str(code).strip()
                
            tomb_val = artifact.get('found_in_tomb', '')
            
            inferred_tomb = None
            if ':' in code:
                parts = code.split(':')
                if parts[0].upper().startswith('M'):
                    inferred_tomb = parts[0].upper()
            
            # 2. 如果 artifact_code 推断出了有效的 M 号，优先使用
            if inferred_tomb:
                artifact['found_in_tomb'] = inferred_tomb
            else:
                # 3. 否则尝试清洗现有的 found_in_tomb
                if not tomb_val or str(tomb_val).lower() in ['全文', 'unknown', 'none', ''] or '号墓' in str(tomb_val):
                    val_str = str(tomb_val) if tomb_val is not None else ''
                    
                    # 尝试匹配 "六号墓" -> "M6"
                    cn_num_map = {'一':1, '二':2, '三':3, '四':4, '五':5, '六':6, '七':7, '八':8, '九':9, '十':10}
                    match = re.search(r'([一二三四五六七八九十]+)号墓', val_str)
                    if match:
                        num_str = match.group(1)
                        # 简单转换 (仅支持1-10，复杂的暂略)
                        num = cn_num_map.get(num_str)
                        if num:
                            artifact['found_in_tomb'] = f"M{num}"
                    else:
                         # 匹配 "6号墓" -> "M6"
                        match_digit = re.search(r'(\d+)号墓', val_str)
                        if match_digit:
                             artifact['found_in_tomb'] = f"M{match_digit.group(1)}"

        # 合并同一文物的信息
        self.db.add_log(task_id, 'INFO', f'合并文物信息...')
        merged_artifacts = self.artifact_merger.merge_artifacts(all_artifacts)
        self.db.add_log(task_id, 'INFO', 
                       f'合并完成: {len(all_artifacts)} -> {len(merged_artifacts)}')
        
        # 准备CIDOC元数据
        analyzer = TemplateAnalyzer(template_path)
        field_metadata = analyzer.get_field_metadata()
        
        # 字段映射：中文 -> 英文，并添加Raw/CIDOC数据
        self.db.add_log(task_id, 'INFO', f'映射字段名并生成CIDOC数据...')
        field_mapper = FieldMapper(template_path)
        
        mapped_artifacts = []
        
        for artifact in merged_artifacts:
            # 1. 生成 Raw Attributes (JSON)
            # 排除系统生成的元数据字段，只保留抽取相关的
            system_fields = ['task_id', 'site_id', 'source_text_blocks', 'extraction_confidence', 'found_in_tomb']
            raw_dict = {k: v for k, v in artifact.items() if k not in system_fields}
            raw_data = json.dumps(raw_dict, ensure_ascii=False)
            
            # 2. 生成 CIDOC Attributes (JSON) 
            # V3.6: 三元组生成已移至 _generate_triples 并改为插入后执行，
            # 但 cidoc_attributes 仍然保留以便兼容查询
            cidoc_dict = {}
            
            for key, value in artifact.items():
                # 只处理模板中定义的字段
                # 尝试直接匹配或归一化匹配
                meta = None
                if key in field_metadata:
                    meta = field_metadata[key]
                else:
                    # 尝试模糊匹配 metadata key
                    import re
                    def clean_string(s): return re.sub(r'\s+', '', str(s)).lower()
                    clean_k = clean_string(key)
                    for mk, mv in field_metadata.items():
                        if clean_string(mk) == clean_k:
                            meta = mv
                            break
                
                if meta:
                    cidoc_dict[key] = {
                        "value": value,
                        "entity_type": meta.get('entity_type'),
                        "property": meta.get('property'),
                        "target_class": meta.get('class')
                    }
                        
            cidoc_json = json.dumps(cidoc_dict, ensure_ascii=False)
            
            # 3. 映射字段
            mapped = field_mapper.map_artifact_fields(artifact)
            
            # 4. 添加新字段
            mapped['raw_attributes'] = raw_data
            mapped['cidoc_attributes'] = cidoc_json
            
            # 保留原始数据以便生成三元组（因为mapped后的key是英文，可能丢失原始中文key导致匹配失败）
            mapped['#original_data'] = artifact 
            
            mapped_artifacts.append(mapped)
            
        self.db.add_log(task_id, 'INFO', f'数据处理完成')
        
        # 关联图片
        self.db.add_log(task_id, 'INFO', f'关联图片...')
        img_manager = ImageManager(report_folder)
        # V3.7: 增加图片资源日志
        if hasattr(img_manager, 'content_list') and img_manager.content_list is not None:
             self.db.add_log(task_id, 'INFO', f'ImageManager加载了 {len(img_manager.content_list)} 个内容项')
        else:
             self.db.add_log(task_id, 'WARNING', 'ImageManager未能加载content_list，图片关联可能受限')
        
        img_linker = ImageLinker(img_manager)
        
        # 插入数据库
        total_triples_count = 0
        linked_images_count = 0 # Track linked images
        
        for artifact in mapped_artifacts:
            # 提取原始数据
            original_data = artifact.pop('#original_data', {})
            
            # 插入文物
            if artifact_type == 'pottery':
                # 陶器清洗规则：
                # 1. 排除明确标记为玉料的 (jade_type 存在且不为空)
                # 2. 排除分类是"玉器"的 (如果 category_level1 存在)
                if artifact.get('jade_type'):
                    self.db.add_log(task_id, 'WARNING', f"剔除错误数据: 在陶器任务中发现玉器特征 ({artifact.get('artifact_code')}, jade_type={artifact.get('jade_type')})")
                    continue
                    
                artifact_id = self.db.insert_pottery(artifact)
                
            elif artifact_type == 'jade':
                # 玉器清洗规则：
                # 1. 排除明确标记为陶土的 (clay_type 存在且不为空)
                # 2. 排除分类明确为陶器的 (category_level1 包含 '陶')
                # 3. 排除玉料类型为陶的 (jade_type 包含 '陶')
                
                # 检查 clay_type
                if artifact.get('clay_type'):
                    self.db.add_log(task_id, 'WARNING', f"剔除错误数据: 在玉器任务中发现陶器特征 ({artifact.get('artifact_code')}, clay_type={artifact.get('clay_type')})")
                    continue
                
                # 检查 category_level1
                cat1 = str(artifact.get('category_level1', '') or '')
                if '陶' in cat1:
                     self.db.add_log(task_id, 'WARNING', f"剔除错误数据: 在玉器任务中发现陶器分类 ({artifact.get('artifact_code')}, category={cat1})")
                     continue

                # 检查 jade_type (排除 "陶" 但允许 "陶土" 出现在描述中? 不，玉器表不应该出现陶材质)
                j_type = str(artifact.get('jade_type', '') or '')
                # 如果 jade_type 是 "陶" 或者包含 "陶器"
                if j_type == '陶' or '陶器' in j_type:
                     self.db.add_log(task_id, 'WARNING', f"剔除错误数据: 在玉器任务中发现非玉材质 ({artifact.get('artifact_code')}, jade_type={j_type})")
                     continue
                
                # 额外检查：如果 artifact_code 和陶器表里的重复，且陶器表里已有 clay_type，那这个很可能是误判
                # (这个检查比较耗时且逻辑复杂，暂不实现，先依赖 clay_type 字段过滤)
                
                artifact_id = self.db.insert_jade(artifact)
            else:
                continue
            
            # V3.6: 生成并插入三元组 (使用原始数据，确保能匹配到中文Template Key)
            # 同时也支持 English Key (因为 _generate_triples 现在支持双向匹配)
            if artifact_id:
                 self._generate_triples(original_data, artifact_type, artifact_id, task_id)

            # 关联图片
            try:
                images = img_linker.link_artifact_to_images(artifact, artifact_type)
                if images:
                    linked_images_count += len(images)
                    
                for img in images:
                    # 查找image_id
                    cursor = self.db.conn.cursor()
                    cursor.execute(
                        'SELECT id FROM images WHERE task_id = ? AND image_hash = ?',
                        (task_id, img['image_hash'])
                    )
                    row = cursor.fetchone()
                    if row:
                        image_id = row[0]
                        self.db.link_artifact_to_image({
                            'artifact_type': artifact_type,
                            'artifact_id': artifact_id,
                            'artifact_code': artifact.get('artifact_code', ''),
                            'image_id': image_id,
                            'image_role': img['image_role'],
                            'display_order': img['display_order'],
                            'confidence': img['confidence']
                        })
                
                # 更新has_images标志
                if images:
                    # Re-query to get the main image ID if needed, or just use the first one found above
                    # Optimize: use the ID from the loop if possible
                    # For now, keep logic simple but robust
                    cursor = self.db.conn.cursor()
                    cursor.execute(
                        'SELECT id FROM images WHERE task_id = ? AND image_hash = ?',
                        (task_id, images[0]['image_hash'])
                    )
                    row = cursor.fetchone()
                    
                    table_name = 'pottery_artifacts' if artifact_type == 'pottery' else 'jade_artifacts'
                    self.db.conn.execute(
                        f'UPDATE {table_name} SET has_images = 1, main_image_id = ? WHERE id = ?',
                        (row[0] if row else None, artifact_id)
                    )
                    self.db.conn.commit()
                    
            except Exception as e:
                self.db.add_log(task_id, 'WARNING', f'图片关联失败: {str(e)}')
        
        self.db.add_log(task_id, 'INFO', f'图片关联完成: 共关联 {linked_images_count} 张')
        
        return len(merged_artifacts)
    
    def get_task_report(self, task_id: str) -> Dict:
        """获取任务报告"""
        return self.db.get_task_summary(task_id)
    
    def close(self):
        """关闭工作流"""
        self.db.close()


# 示例用法
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='执行文物抽取工作流')
    parser.add_argument('--report', required=True, help='报告文件夹路径')
    parser.add_argument('--pottery-template', help='陶器模板路径')
    parser.add_argument('--jade-template', help='玉器模板路径')
    parser.add_argument('--site-template', help='遗址模板路径')
    parser.add_argument('--period-template', help='时期模板路径')
    
    args = parser.parse_args()
    
    # 构建模板映射
    templates = {}
    if args.pottery_template:
        templates['pottery'] = args.pottery_template
    if args.jade_template:
        templates['jade'] = args.jade_template
    if args.site_template:
        templates['site'] = args.site_template
    if args.period_template:
        templates['period'] = args.period_template
    
    # 执行工作流
    workflow = ExtractionWorkflow()
    
    try:
        print(f"开始抽取: {args.report}")
        task_id = workflow.execute_full_extraction(args.report, templates)
        print(f"\n✅ 抽取完成！任务ID: {task_id}")
        
        # 显示报告
        report = workflow.get_task_report(task_id)
        print(f"\n任务报告:")
        print(f"  遗址: {report['site']['site_name'] if report.get('site') else '未抽取'}")
        print(f"  陶器: {report['total_pottery']}件 (含图片: {report['pottery_with_images']})")
        print(f"  玉器: {report['total_jade']}件 (含图片: {report['jade_with_images']})")
        print(f"  图片: {report['total_images']}张")
        
    finally:
        workflow.close()

