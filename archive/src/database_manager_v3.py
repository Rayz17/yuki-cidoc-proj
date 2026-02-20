"""
数据库管理器 V3.0
支持多主体（遗址、时期、陶器、玉器）和图片管理
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any


class DatabaseManagerV3:
    """
    数据库管理器V3.0
    支持遗址、时期、陶器、玉器四主体及图片管理
    """
    
    def __init__(self, db_path: str = 'database/artifacts_v3.db'):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self.conn = None
        
        # 确保数据库目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
    
    def connect(self):
        """建立数据库连接"""
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row  # 使用Row对象，支持字典访问
    
    def close(self):
        """关闭数据库连接"""
        if self.conn:
            self.conn.close()
            self.conn = None
    
    def initialize_database(self):
        """初始化数据库（执行schema脚本）"""
        schema_path = 'database/schema_v3.sql'
        
        if not os.path.exists(schema_path):
            raise FileNotFoundError(f"Schema文件不存在: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        
        cursor = self.conn.cursor()
        cursor.executescript(schema_sql)
        self.conn.commit()
        
        print(f"✅ 数据库初始化完成: {self.db_path}")
    
    def _get_table_columns(self, table_name: str) -> List[str]:
        """获取表的列名列表"""
        cursor = self.conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name})")
        return [row['name'] for row in cursor.fetchall()]

    def _filter_valid_data(self, table_name: str, data: Dict) -> Dict:
        """
        过滤掉表中不存在的字段
        这可以防止因为Prompt生成了数据库中不存在的字段而导致插入失败
        """
        valid_columns = set(self._get_table_columns(table_name))
        filtered_data = {}
        ignored_fields = []
        
        for k, v in data.items():
            if k in valid_columns:
                # V3.6 Fix: 自动序列化列表/字典为JSON字符串
                if isinstance(v, (list, dict)):
                    filtered_data[k] = json.dumps(v, ensure_ascii=False)
                else:
                    filtered_data[k] = v
            else:
                ignored_fields.append(k)
        
        if ignored_fields:
            # print(f"⚠️ 警告: 表 {table_name} 中不存在以下字段，将被忽略: {ignored_fields}")
            pass
            
        return filtered_data

    # ========== 任务管理 ==========
    
    def create_task(self, task_data: Dict) -> str:
        """
        创建抽取任务
        
        Args:
            task_data: 任务数据字典
        
        Returns:
            task_id: 任务ID
        """
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO extraction_tasks (
                task_id, report_name, report_folder_path,
                pdf_path, markdown_path, layout_json_path,
                content_list_json_path, images_folder_path,
                extraction_config, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            task_data['task_id'],
            task_data['report_name'],
            task_data['report_folder_path'],
            task_data.get('pdf_path'),
            task_data.get('markdown_path'),
            task_data.get('layout_json_path'),
            task_data.get('content_list_json_path'),
            task_data.get('images_folder_path'),
            json.dumps(task_data.get('extraction_config', {})),
            task_data.get('notes', '')
        ))
        
        self.conn.commit()
        return task_data['task_id']
    
    def update_task_status(self, task_id: str, status: str):
        """更新任务状态"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE extraction_tasks 
            SET status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        ''', (status, task_id))
        self.conn.commit()
    
    def update_task_statistics(self, task_id: str, stats: Dict):
        """更新任务统计信息"""
        cursor = self.conn.cursor()
        cursor.execute('''
            UPDATE extraction_tasks 
            SET total_pottery = ?, total_jade = ?, 
                total_periods = ?, total_images = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE task_id = ?
        ''', (
            stats.get('total_pottery', 0),
            stats.get('total_jade', 0),
            stats.get('total_periods', 0),
            stats.get('total_images', 0),
            task_id
        ))
        self.conn.commit()
    
    def get_task(self, task_id: str) -> Optional[Dict]:
        """获取任务信息"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM extraction_tasks WHERE task_id = ?', (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def get_all_tasks(self) -> List[Dict]:
        """获取所有任务"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM extraction_tasks ORDER BY created_at DESC')
        return [dict(row) for row in cursor.fetchall()]
    
    def add_log(self, task_id: str, level: str, message: str):
        """添加日志"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT INTO extraction_logs (task_id, log_level, message)
            VALUES (?, ?, ?)
        ''', (task_id, level, message))
        self.conn.commit()
    
    # ========== 遗址管理 ==========
    
    def get_site_by_report(self, report_folder: str) -> Optional[Dict]:
        """根据报告文件夹查找已存在的遗址"""
        cursor = self.conn.cursor()
        # 通过关联任务表来查找
        cursor.execute('''
            SELECT s.* FROM sites s
            JOIN extraction_tasks t ON s.task_id = t.task_id
            WHERE t.report_folder_path = ?
            ORDER BY s.created_at DESC
            LIMIT 1
        ''', (report_folder,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def get_site_by_name(self, site_name: str) -> Optional[Dict]:
        """
        根据遗址名称查找遗址（用于跨报告合并）
        支持模糊匹配，例如 '反山' 可以匹配 '反山遗址'
        """
        cursor = self.conn.cursor()
        # 1. 尝试精确匹配
        cursor.execute('SELECT * FROM sites WHERE site_name = ? LIMIT 1', (site_name,))
        row = cursor.fetchone()
        if row:
            return dict(row)
            
        # 2. 尝试包含匹配 (如果输入的site_name较长，比如'良渚古城反山遗址'，而库里是'反山')
        # 或者库里是 '良渚古城反山遗址'，输入是 '反山'
        cursor.execute('''
            SELECT * FROM sites 
            WHERE site_name LIKE ? OR ? LIKE ('%' || site_name || '%')
            LIMIT 1
        ''', (f'%{site_name}%', site_name))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    def insert_site(self, site_data: Dict) -> int:
        """插入遗址信息"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO sites (
                task_id, site_code, site_name, site_alias, site_type,
                current_location, geographic_coordinates, elevation,
                total_area, excavated_area, culture_name, absolute_dating,
                protection_level, preservation_status,
                source_text_blocks, extraction_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            site_data['task_id'],
            site_data.get('site_code'),
            site_data['site_name'],
            site_data.get('site_alias'),
            site_data.get('site_type'),
            site_data.get('current_location'),
            site_data.get('geographic_coordinates'),
            site_data.get('elevation'),
            site_data.get('total_area'),
            site_data.get('excavated_area'),
            site_data.get('culture_name'),
            site_data.get('absolute_dating'),
            site_data.get('protection_level'),
            site_data.get('preservation_status'),
            site_data.get('source_text_blocks'),
            site_data.get('extraction_confidence', 0.0)
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def update_site(self, site_id: int, site_data: Dict):
        """
        更新遗址信息
        自动过滤无效字段
        """
        cursor = self.conn.cursor()
        
        # 过滤无效字段
        valid_data = self._filter_valid_data('sites', site_data)
        
        # 动态构建更新语句
        fields = [k for k in valid_data.keys() if k not in ['id', 'created_at']]
        
        if not fields:
            return
            
        set_clause = ", ".join([f"{f} = ?" for f in fields])
        values = [valid_data[f] for f in fields]
        values.append(site_id)
        
        sql = f'UPDATE sites SET {set_clause} WHERE id = ?'
        cursor.execute(sql, values)
        self.conn.commit()

    def get_site_by_task(self, task_id: str) -> Optional[Dict]:
        """根据任务ID获取遗址信息"""
        cursor = self.conn.cursor()
        cursor.execute('SELECT * FROM sites WHERE task_id = ?', (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    
    # ========== 遗址结构管理 ==========
    
    def insert_structure(self, structure_data: Dict) -> int:
        """插入遗址结构"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO site_structures (
                site_id, parent_id, structure_level, structure_code,
                structure_name, structure_type, relative_position,
                coordinates, length, width, depth, area,
                description, features, source_text_blocks
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            structure_data['site_id'],
            structure_data.get('parent_id'),
            structure_data.get('structure_level'),
            structure_data.get('structure_code'),
            structure_data.get('structure_name'),
            structure_data.get('structure_type'),
            structure_data.get('relative_position'),
            structure_data.get('coordinates'),
            structure_data.get('length'),
            structure_data.get('width'),
            structure_data.get('depth'),
            structure_data.get('area'),
            structure_data.get('description'),
            structure_data.get('features'),
            structure_data.get('source_text_blocks')
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_structures_by_site(self, site_id: int) -> List[Dict]:
        """获取遗址的所有结构"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM site_structures 
            WHERE site_id = ? 
            ORDER BY structure_level, structure_code
        ''', (site_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def get_structure_by_name(self, site_id: int, name: str) -> Optional[Dict]:
        """根据名称查找结构"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM site_structures 
            WHERE site_id = ? AND structure_name = ?
            LIMIT 1
        ''', (site_id, name))
        row = cursor.fetchone()
        return dict(row) if row else None

    def update_structure(self, structure_id: int, structure_data: Dict):
        """更新遗址结构"""
        cursor = self.conn.cursor()
        
        valid_data = self._filter_valid_data('site_structures', structure_data)
        fields = [k for k in valid_data.keys() if k not in ['id', 'created_at']]
        
        if not fields:
            return
            
        set_clause = ", ".join([f"{f} = ?" for f in fields])
        values = [valid_data[f] for f in fields]
        values.append(structure_id)
        
        sql = f'UPDATE site_structures SET {set_clause} WHERE id = ?'
        cursor.execute(sql, values)
        self.conn.commit()
    
    # ========== 时期管理 ==========
    
    def insert_period(self, period_data: Dict) -> int:
        """插入时期信息"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT INTO periods (
                task_id, site_id, period_code, period_name, period_alias,
                time_span_start, time_span_end, absolute_dating, relative_dating,
                development_stage, phase_sequence, characteristics,
                representative_artifacts, source_text_blocks, extraction_confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            period_data['task_id'],
            period_data['site_id'],
            period_data.get('period_code'),
            period_data.get('period_name', '未命名时期'), # 使用 .get() 并提供默认值
            period_data.get('period_alias'),
            period_data.get('time_span_start'),
            period_data.get('time_span_end'),
            period_data.get('absolute_dating'),
            period_data.get('relative_dating'),
            period_data.get('development_stage'),
            period_data.get('phase_sequence'),
            period_data.get('characteristics'),
            period_data.get('representative_artifacts'),
            period_data.get('source_text_blocks'),
            period_data.get('extraction_confidence', 0.0)
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_periods_by_site(self, site_id: int) -> List[Dict]:
        """获取遗址的所有时期"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM periods 
            WHERE site_id = ? 
            ORDER BY phase_sequence
        ''', (site_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ========== 陶器管理 ==========
    
    def insert_pottery(self, pottery_data: Dict) -> int:
        """插入或更新陶器信息 (Upsert based on site_id + artifact_code)"""
        cursor = self.conn.cursor()
        
        # 过滤无效字段
        valid_data = self._filter_valid_data('pottery_artifacts', pottery_data)
        
        # 检查是否已存在 (site_id + artifact_code)
        site_id = valid_data.get('site_id')
        artifact_code = valid_data.get('artifact_code')
        
        existing_id = None
        if site_id and artifact_code:
            cursor.execute(
                'SELECT id FROM pottery_artifacts WHERE site_id = ? AND artifact_code = ?',
                (site_id, artifact_code)
            )
            row = cursor.fetchone()
            if row:
                existing_id = row['id']
        
        # 动态构建字段列表
        fields = list(valid_data.keys())
        
        if existing_id:
            # 更新逻辑
            # 不更新 task_id, site_id, artifact_code, created_at
            update_fields = [f for f in fields if f not in ['id', 'task_id', 'site_id', 'artifact_code', 'created_at']]
            set_clause = ", ".join([f"{f} = ?" for f in update_fields])
            values = [valid_data[f] for f in update_fields]
            values.append(existing_id)
            
            sql = f'UPDATE pottery_artifacts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
            cursor.execute(sql, values)
            self.conn.commit()
            return existing_id
        else:
            # 插入逻辑 (使用 ON CONFLICT DO UPDATE)
            placeholders = ['?' for _ in fields]
            values = [valid_data[f] for f in fields]
            
            # 仅当site_id和artifact_code都存在时，使用UPSERT
            # 否则使用普通INSERT
            if 'site_id' in fields and 'artifact_code' in fields:
                # 构建更新子句
                update_fields = [f for f in fields if f not in ['id', 'task_id', 'site_id', 'artifact_code', 'created_at']]
                update_clause = ", ".join([f"{f} = excluded.{f}" for f in update_fields])
                
                sql = f'''
                    INSERT INTO pottery_artifacts ({", ".join(fields)})
                    VALUES ({", ".join(placeholders)})
                    ON CONFLICT(site_id, artifact_code) DO UPDATE SET
                    {update_clause}, updated_at = CURRENT_TIMESTAMP
                '''
            else:
                sql = f'''
                    INSERT INTO pottery_artifacts ({", ".join(fields)})
                    VALUES ({", ".join(placeholders)})
                '''
                
            cursor.execute(sql, values)
            self.conn.commit()
            # 如果是更新，lastrowid可能不准，但我们只需要ID
            # 这种情况下，我们需要查询回ID
            if cursor.lastrowid:
                return cursor.lastrowid
            elif 'site_id' in fields and 'artifact_code' in fields:
                # 查询ID
                cursor.execute(
                    'SELECT id FROM pottery_artifacts WHERE site_id = ? AND artifact_code = ?',
                    (valid_data['site_id'], valid_data['artifact_code'])
                )
                row = cursor.fetchone()
                return row['id'] if row else 0
            return 0

    def get_pottery_by_task(self, task_id: str) -> List[Dict]:
        """获取任务的所有陶器"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM pottery_artifacts 
            WHERE task_id = ? 
            ORDER BY artifact_code
        ''', (task_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ========== 玉器管理 ==========
    
    def insert_jade(self, jade_data: Dict) -> int:
        """插入或更新玉器信息 (Upsert based on site_id + artifact_code)"""
        cursor = self.conn.cursor()
        
        # 过滤无效字段
        valid_data = self._filter_valid_data('jade_artifacts', jade_data)
        
        # 检查是否已存在 (site_id + artifact_code)
        site_id = valid_data.get('site_id')
        artifact_code = valid_data.get('artifact_code')
        
        existing_id = None
        if site_id and artifact_code:
            cursor.execute(
                'SELECT id FROM jade_artifacts WHERE site_id = ? AND artifact_code = ?',
                (site_id, artifact_code)
            )
            row = cursor.fetchone()
            if row:
                existing_id = row['id']
        
        # 动态构建字段列表
        fields = list(valid_data.keys())
        
        if existing_id:
            # 更新逻辑
            update_fields = [f for f in fields if f not in ['id', 'task_id', 'site_id', 'artifact_code', 'created_at']]
            set_clause = ", ".join([f"{f} = ?" for f in update_fields])
            values = [valid_data[f] for f in update_fields]
            values.append(existing_id)
            
            sql = f'UPDATE jade_artifacts SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?'
            cursor.execute(sql, values)
            self.conn.commit()
            return existing_id
        else:
            # 插入逻辑 (使用 ON CONFLICT DO UPDATE)
            placeholders = ['?' for _ in fields]
            values = [valid_data[f] for f in fields]
            
            if 'site_id' in fields and 'artifact_code' in fields:
                # 构建更新子句
                update_fields = [f for f in fields if f not in ['id', 'task_id', 'site_id', 'artifact_code', 'created_at']]
                update_clause = ", ".join([f"{f} = excluded.{f}" for f in update_fields])
                
                sql = f'''
                    INSERT INTO jade_artifacts ({", ".join(fields)})
                    VALUES ({", ".join(placeholders)})
                    ON CONFLICT(site_id, artifact_code) DO UPDATE SET
                    {update_clause}, updated_at = CURRENT_TIMESTAMP
                '''
            else:
                sql = f'''
                    INSERT INTO jade_artifacts ({", ".join(fields)})
                    VALUES ({", ".join(placeholders)})
                '''
            
            cursor.execute(sql, values)
            self.conn.commit()
            
            if cursor.lastrowid:
                return cursor.lastrowid
            elif 'site_id' in fields and 'artifact_code' in fields:
                # 查询ID
                cursor.execute(
                    'SELECT id FROM jade_artifacts WHERE site_id = ? AND artifact_code = ?',
                    (valid_data['site_id'], valid_data['artifact_code'])
                )
                row = cursor.fetchone()
                return row['id'] if row else 0
            return 0

    def get_jade_by_task(self, task_id: str) -> List[Dict]:
        """获取任务的所有玉器"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM jade_artifacts 
            WHERE task_id = ? 
            ORDER BY artifact_code
        ''', (task_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    # ========== 图片管理 ==========
    
    def insert_image(self, image_data: Dict) -> int:
        """插入图片信息"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO images (
                task_id, image_hash, image_path, image_type,
                page_idx, bbox, caption, related_text,
                file_size, width, height
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            image_data['task_id'],
            image_data['image_hash'],
            image_data['image_path'],
            image_data.get('image_type'),
            image_data.get('page_idx'),
            image_data.get('bbox'),
            image_data.get('caption'),
            image_data.get('related_text'),
            image_data.get('file_size'),
            image_data.get('width'),
            image_data.get('height')
        ))
        
        self.conn.commit()
        return cursor.lastrowid
    
    def get_images_by_task(self, task_id: str) -> List[Dict]:
        """获取任务的所有图片"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT * FROM images 
            WHERE task_id = ? 
            ORDER BY page_idx
        ''', (task_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def link_artifact_to_image(self, link_data: Dict):
        """关联文物与图片"""
        cursor = self.conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO artifact_images (
                artifact_type, artifact_id, artifact_code,
                image_id, image_role, display_order,
                description, extraction_method, confidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            link_data['artifact_type'],
            link_data['artifact_id'],
            link_data['artifact_code'],
            link_data['image_id'],
            link_data['image_role'],
            link_data.get('display_order', 0),
            link_data.get('description'),
            link_data.get('extraction_method', 'auto'),
            link_data.get('confidence', 0.0)
        ))
        
        self.conn.commit()
    
    def get_artifact_images(self, artifact_id: int, artifact_type: str) -> List[Dict]:
        """获取文物的所有图片"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT ai.*, i.image_path, i.image_hash, i.caption, i.page_idx
            FROM artifact_images ai
            JOIN images i ON i.id = ai.image_id
            WHERE ai.artifact_id = ? AND ai.artifact_type = ?
            ORDER BY ai.display_order
        ''', (artifact_id, artifact_type))
        return [dict(row) for row in cursor.fetchall()]
    
    # ========== 关系管理 ==========
    
    def link_artifact_to_period(self, artifact_type: str, artifact_id: int, 
                                period_id: int, confidence: float = 1.0, evidence: str = ''):
        """关联文物与时期"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO artifact_period_mapping (
                artifact_type, artifact_id, period_id, confidence, evidence
            ) VALUES (?, ?, ?, ?, ?)
        ''', (artifact_type, artifact_id, period_id, confidence, evidence))
        self.conn.commit()
    
    def link_artifact_to_location(self, artifact_type: str, artifact_id: int,
                                  structure_id: int, location_type: str = 'excavation',
                                  description: str = ''):
        """关联文物与位置"""
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO artifact_location_mapping (
                artifact_type, artifact_id, structure_id, location_type, description
            ) VALUES (?, ?, ?, ?, ?)
        ''', (artifact_type, artifact_id, structure_id, location_type, description))
        self.conn.commit()

    # ========== 元数据管理 (V3.2) ==========

    def register_template_mappings(self, mappings: List[Dict]):
        """
        注册模版映射 (UPSERT)
        如果映射已存在则更新，否则插入
        
        Args:
            mappings: List of dicts containing:
                - artifact_type
                - field_name_cn
                - field_name_en
                - description
                - cidoc_entity
                - cidoc_property
                - target_class
        """
        cursor = self.conn.cursor()
        
        # 使用 ON CONFLICT DO UPDATE 保持 ID 不变
        sql = '''
            INSERT INTO sys_template_mappings (
                artifact_type, field_name_cn, field_name_en,
                description, cidoc_entity, cidoc_property, target_class
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(artifact_type, field_name_cn) DO UPDATE SET
                field_name_en=excluded.field_name_en,
                description=excluded.description,
                cidoc_entity=excluded.cidoc_entity,
                cidoc_property=excluded.cidoc_property,
                target_class=excluded.target_class
        '''
        
        params = [(
            m['artifact_type'],
            m['field_name_cn'],
            m.get('field_name_en'),
            m.get('description'),
            m.get('cidoc_entity'),
            m.get('cidoc_property'),
            m.get('target_class')
        ) for m in mappings]
        
        cursor.executemany(sql, params)
        self.conn.commit()

    def get_template_mapping_ids(self, artifact_type: str) -> Dict[str, int]:
        """
        获取指定文物类型的模版映射ID表
        Returns: { '陶土种类': 1, '口径': 2, ... }
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT field_name_cn, id 
            FROM sys_template_mappings 
            WHERE artifact_type = ?
        ''', (artifact_type,))
        return {row['field_name_cn']: row['id'] for row in cursor.fetchall()}

    # ========== 语义事实管理 (V3.2) ==========

    def insert_fact_triples(self, triples: List[Dict]):
        """
        批量插入语义事实三元组
        
        Args:
            triples: List of dicts containing:
                - artifact_type
                - artifact_id
                - mapping_id
                - predicate (optional)
                - object_value
                - confidence (optional)
        """
        if not triples:
            return
            
        cursor = self.conn.cursor()
        
        sql = '''
            INSERT INTO fact_artifact_triples (
                artifact_type, artifact_id, mapping_id,
                predicate, object_value, confidence
            ) VALUES (?, ?, ?, ?, ?, ?)
        '''
        
        params = [(
            t['artifact_type'],
            t['artifact_id'],
            t['mapping_id'],
            t.get('predicate'),
            str(t['object_value']),  # Ensure string format
            t.get('confidence', 1.0)
        ) for t in triples]
        
        cursor.executemany(sql, params)
        self.conn.commit()

    # ========== 查询功能 ==========
    
    def get_artifacts_by_period(self, period_id: int, artifact_type: str = None) -> List[Dict]:
        """查询某时期的文物"""
        cursor = self.conn.cursor()
        
        if artifact_type == 'pottery':
            cursor.execute('''
                SELECT p.* FROM pottery_artifacts p
                JOIN artifact_period_mapping m ON m.artifact_id = p.id AND m.artifact_type = 'pottery'
                WHERE m.period_id = ?
            ''', (period_id,))
        elif artifact_type == 'jade':
            cursor.execute('''
                SELECT j.* FROM jade_artifacts j
                JOIN artifact_period_mapping m ON m.artifact_id = j.id AND m.artifact_type = 'jade'
                WHERE m.period_id = ?
            ''', (period_id,))
        else:
            # 返回所有类型
            pottery = self.get_artifacts_by_period(period_id, 'pottery')
            jade = self.get_artifacts_by_period(period_id, 'jade')
            return pottery + jade
        
        return [dict(row) for row in cursor.fetchall()]
    
    def get_task_summary(self, task_id: str) -> Dict:
        """获取任务摘要"""
        task = self.get_task(task_id)
        if not task:
            return {}
        
        site = self.get_site_by_task(task_id)
        pottery = self.get_pottery_by_task(task_id)
        jade = self.get_jade_by_task(task_id)
        images = self.get_images_by_task(task_id)
        
        return {
            'task': task,
            'site': site,
            'total_pottery': len(pottery),
            'total_jade': len(jade),
            'total_images': len(images),
            'pottery_with_images': sum(1 for p in pottery if p.get('has_images')),
            'jade_with_images': sum(1 for j in jade if j.get('has_images'))
        }


# 示例用法
if __name__ == "__main__":
    db = DatabaseManagerV3('database/test_v3.db')
    db.connect()
    
    # 初始化数据库
    db.initialize_database()
    
    # 创建测试任务
    task_id = 'test_' + datetime.now().strftime('%Y%m%d_%H%M%S')
    db.create_task({
        'task_id': task_id,
        'report_name': '测试报告',
        'report_folder_path': '/path/to/report'
    })
    
    print(f"✅ 创建任务: {task_id}")
    
    # 查询任务
    task = db.get_task(task_id)
    print(f"任务信息: {task['report_name']}, 状态: {task['status']}")
    
    db.close()
    print("\n✅ 数据库管理器测试完成")

