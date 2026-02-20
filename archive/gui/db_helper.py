"""
数据库辅助类
提供GUI所需的所有数据库查询功能
"""

import sqlite3
import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime


class DatabaseHelper:
    """
    数据库辅助类
    封装所有GUI需要的数据库查询操作
    """
    
    def __init__(self, db_path: str):
        """
        初始化数据库辅助类
        
        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # ========== 任务管理 ==========
    
    def get_all_tasks(self, status_filter: Optional[List[str]] = None) -> List[Dict]:
        """
        获取所有任务
        
        Args:
            status_filter: 状态筛选列表
        
        Returns:
            任务列表
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if status_filter:
            placeholders = ','.join('?' * len(status_filter))
            query = f'''
                SELECT * FROM extraction_tasks 
                WHERE status IN ({placeholders})
                ORDER BY created_at DESC
            '''
            cursor.execute(query, status_filter)
        else:
            cursor.execute('SELECT * FROM extraction_tasks ORDER BY created_at DESC')
        
        tasks = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return tasks
    
    def delete_task(self, task_id: str) -> bool:
        """
        删除任务及其相关数据
        
        Args:
            task_id: 任务ID
        
        Returns:
            是否删除成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            # 删除任务日志
            cursor.execute('DELETE FROM extraction_logs WHERE task_id = ?', (task_id,))
            
            # 删除任务
            cursor.execute('DELETE FROM extraction_tasks WHERE task_id = ?', (task_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            print(f"删除任务失败: {e}")
            return False
            
    def abort_task(self, task_id: str) -> bool:
        """
        中止任务（将状态设置为aborted）
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否操作成功
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.execute("UPDATE extraction_tasks SET status = 'aborted', updated_at = CURRENT_TIMESTAMP WHERE task_id = ?", (task_id,))
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            conn.close()
            print(f"中止任务失败: {e}")
            return False
    
    def get_task_detail(self, task_id: str) -> Optional[Dict]:
        """获取任务详情"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM extraction_tasks WHERE task_id = ?', (task_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_task_logs(self, task_id: str, level_filter: Optional[List[str]] = None) -> List[Dict]:
        """获取任务日志"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if level_filter:
            placeholders = ','.join('?' * len(level_filter))
            query = f'''
                SELECT * FROM extraction_logs 
                WHERE task_id = ? AND log_level IN ({placeholders})
                ORDER BY created_at DESC
            '''
            cursor.execute(query, [task_id] + level_filter)
        else:
            cursor.execute('''
                SELECT * FROM extraction_logs 
                WHERE task_id = ? 
                ORDER BY created_at DESC
            ''', (task_id,))
        
        logs = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return logs
    
    def get_task_summary(self, task_id: str) -> Dict:
        """获取任务摘要"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 获取任务信息
        cursor.execute('SELECT * FROM extraction_tasks WHERE task_id = ?', (task_id,))
        task = dict(cursor.fetchone())
        
        # 获取遗址信息
        cursor.execute('SELECT * FROM sites WHERE task_id = ?', (task_id,))
        site_row = cursor.fetchone()
        site = dict(site_row) if site_row else None
        
        # 获取统计
        cursor.execute('SELECT COUNT(*) as count FROM pottery_artifacts WHERE task_id = ?', (task_id,))
        pottery_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM jade_artifacts WHERE task_id = ?', (task_id,))
        jade_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM images WHERE task_id = ?', (task_id,))
        image_count = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'task': task,
            'site': site,
            'total_pottery': pottery_count,
            'total_jade': jade_count,
            'total_images': image_count
        }
    
    # ========== 遗址管理 ==========
    
    def get_all_sites(self) -> List[Dict]:
        """获取所有遗址"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sites ORDER BY created_at DESC')
        sites = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return sites
    
    def get_site_by_id(self, site_id: int) -> Optional[Dict]:
        """根据ID获取遗址"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sites WHERE id = ?', (site_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_site_structures(self, site_id: int) -> List[Dict]:
        """获取遗址结构"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM site_structures 
            WHERE site_id = ? 
            ORDER BY structure_level, structure_code
        ''', (site_id,))
        structures = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return structures
    
    def get_site_periods(self, site_id: int) -> List[Dict]:
        """获取遗址的时期"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM periods 
            WHERE site_id = ? 
            ORDER BY phase_sequence
        ''', (site_id,))
        periods = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return periods
    
    # ========== 文物管理 ==========
    
    def get_artifacts(self, artifact_type: str, filters: Optional[Dict] = None, 
                     limit: int = -1, offset: int = 0) -> Tuple[List[Dict], int]:
        """
        获取文物列表
        
        Args:
            artifact_type: 'pottery' 或 'jade'
            filters: 筛选条件
            limit: 每页数量 (默认-1表示不限制)
            offset: 偏移量
        
        Returns:
            (文物列表, 总数)
        """
        table_name = 'pottery_artifacts' if artifact_type == 'pottery' else 'jade_artifacts'
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 构建查询
        where_clauses = []
        params = []
        
        if filters:
            if filters.get('task_id'):
                where_clauses.append('task_id = ?')
                params.append(filters['task_id'])
            
            if filters.get('site_id'):
                where_clauses.append('site_id = ?')
                params.append(filters['site_id'])
            
            if filters.get('has_images'):
                where_clauses.append('has_images = 1')
            
            if filters.get('search'):
                where_clauses.append('(artifact_code LIKE ? OR subtype LIKE ?)')
                search_term = f"%{filters['search']}%"
                params.extend([search_term, search_term])
        
        where_sql = ' AND '.join(where_clauses) if where_clauses else '1=1'
        
        # 获取总数
        cursor.execute(f'SELECT COUNT(*) as count FROM {table_name} WHERE {where_sql}', params)
        total = cursor.fetchone()['count']
        
        # 获取数据
        query = f'''
            SELECT * FROM {table_name} 
            WHERE {where_sql}
            ORDER BY id DESC
            LIMIT ? OFFSET ?
        '''
        cursor.execute(query, params + [limit, offset])
        artifacts = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return artifacts, total
    
    def get_artifact_detail(self, artifact_id: int, artifact_type: str) -> Optional[Dict]:
        """获取文物详情"""
        table_name = 'pottery_artifacts' if artifact_type == 'pottery' else 'jade_artifacts'
        
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f'SELECT * FROM {table_name} WHERE id = ?', (artifact_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_artifact_images(self, artifact_id: int, artifact_type: str) -> List[Dict]:
        """获取文物的所有图片"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT ai.*, i.image_path, i.image_hash, i.caption, i.page_idx
            FROM artifact_images ai
            JOIN images i ON i.id = ai.image_id
            WHERE ai.artifact_id = ? AND ai.artifact_type = ?
            ORDER BY ai.display_order
        ''', (artifact_id, artifact_type))
        images = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return images
    
    def get_artifact_triples(self, artifact_id: int, artifact_type: str) -> List[Dict]:
        """
        获取文物的语义三元组 (V3.2)
        返回包含映射信息的丰富三元组
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT 
                f.id, f.predicate, f.object_value, f.confidence,
                m.field_name_cn, m.description, m.cidoc_entity, m.cidoc_property, m.target_class
            FROM fact_artifact_triples f
            JOIN sys_template_mappings m ON f.mapping_id = m.id
            WHERE f.artifact_id = ? AND f.artifact_type = ?
            ORDER BY m.id
        ''', (artifact_id, artifact_type))
        triples = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return triples

    # ========== 图片管理 ==========
    
    def get_all_images(self, task_id: Optional[str] = None, 
                      limit: int = 100, offset: int = 0) -> Tuple[List[Dict], int]:
        """获取图片列表"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if task_id:
            # 获取总数
            cursor.execute('SELECT COUNT(*) as count FROM images WHERE task_id = ?', (task_id,))
            total = cursor.fetchone()['count']
            
            # 获取数据
            cursor.execute('''
                SELECT * FROM images 
                WHERE task_id = ?
                ORDER BY page_idx, id
                LIMIT ? OFFSET ?
            ''', (task_id, limit, offset))
        else:
            # 获取总数
            cursor.execute('SELECT COUNT(*) as count FROM images')
            total = cursor.fetchone()['count']
            
            # 获取数据
            cursor.execute('''
                SELECT * FROM images 
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
        
        images = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return images, total
    
    def get_image_detail(self, image_id: int) -> Optional[Dict]:
        """获取图片详情"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM images WHERE id = ?', (image_id,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None
    
    def get_image_artifacts(self, image_id: int) -> List[Dict]:
        """获取图片关联的文物"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM artifact_images 
            WHERE image_id = ?
            ORDER BY display_order
        ''', (image_id,))
        links = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return links
    
    def get_template_mappings(self, artifact_type: str = None) -> List[Dict]:
        """获取模版映射定义 (V3.2)"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if artifact_type:
            cursor.execute('''
                SELECT * FROM sys_template_mappings 
                WHERE artifact_type = ? 
                ORDER BY id
            ''', (artifact_type,))
        else:
            cursor.execute('SELECT * FROM sys_template_mappings ORDER BY artifact_type, id')
            
        mappings = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return mappings

    # ========== 统计功能 ==========
    
    def get_statistics(self) -> Dict:
        """获取系统统计信息"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 任务统计
        cursor.execute('SELECT COUNT(*) as count FROM extraction_tasks')
        task_count = cursor.fetchone()['count']
        
        cursor.execute("SELECT COUNT(*) as count FROM extraction_tasks WHERE status = 'completed'")
        completed_task_count = cursor.fetchone()['count']
        
        # 遗址统计
        cursor.execute('SELECT COUNT(*) as count FROM sites')
        site_count = cursor.fetchone()['count']
        
        # 文物统计
        cursor.execute('SELECT COUNT(*) as count FROM pottery_artifacts')
        pottery_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM jade_artifacts')
        jade_count = cursor.fetchone()['count']
        
        # 图片统计
        cursor.execute('SELECT COUNT(*) as count FROM images')
        image_count = cursor.fetchone()['count']
        
        cursor.execute('''
            SELECT COUNT(DISTINCT artifact_id) as count 
            FROM artifact_images
        ''')
        artifacts_with_images = cursor.fetchone()['count']
        
        conn.close()
        
        return {
            'task_count': task_count,
            'completed_task_count': completed_task_count,
            'site_count': site_count,
            'pottery_count': pottery_count,
            'jade_count': jade_count,
            'artifact_count': pottery_count + jade_count,
            'image_count': image_count,
            'artifacts_with_images': artifacts_with_images
        }
    
    def get_table_list(self) -> List[str]:
        """获取所有表名"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row['name'] for row in cursor.fetchall()]
        conn.close()
        return tables
    
    def get_table_data(self, table_name: str, limit: int = -1, offset: int = 0, search_term: str = None, search_col: str = None) -> Tuple[List[Dict], List[str], int]:
        """
        获取表数据 (支持分页和搜索)
        
        Returns:
            (数据列表, 列名列表, 总数)
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 获取列名
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row['name'] for row in cursor.fetchall()]
        
        # 构建查询条件
        where_clause = "1=1"
        params = []
        if search_term and search_col:
             where_clause = f"{search_col} LIKE ?"
             params.append(f"%{search_term}%")
             
        # 获取总数
        count_query = f"SELECT COUNT(*) as count FROM {table_name} WHERE {where_clause}"
        cursor.execute(count_query, params)
        total = cursor.fetchone()['count']

        # 获取数据
        data_query = f"SELECT * FROM {table_name} WHERE {where_clause} LIMIT ? OFFSET ?"
        cursor.execute(data_query, params + [limit, offset])
        data = [dict(row) for row in cursor.fetchall()]
        
        conn.close()
        return data, columns, total


# 列名映射字典
COLUMN_MAPPINGS = {
    'extraction_tasks': {
        'id': 'ID',
        'task_id': '任务ID',
        'report_name': '报告名称',
        'status': '状态',
        'total_pottery': '陶器数',
        'total_jade': '玉器数',
        'total_images': '图片数',
        'created_at': '创建时间',
        'updated_at': '更新时间'
    },
    'sites': {
        'id': 'ID',
        'site_code': '遗址编号',
        'site_name': '遗址名称',
        'site_type': '遗址类型',
        'current_location': '地理位置',
        'geographic_coordinates': '地理坐标',
        'spatial_data': '空间数据',
        'elevation': '海拔',
        'culture_name': '文化名称',
        'absolute_dating': '绝对年代',
        'total_area': '总面积',
        'excavated_area': '发掘面积',
        'protection_level': '保护级别',
        'preservation_status': '保存状况',
        'description': '遗址描述'
    },
    'periods': {
        'id': 'ID',
        'period_code': '时期编号',
        'period_name': '时期名称',
        'period_alias': '时期别名',
        'sub_period': '细分时期',
        'historical_era': '历史朝代',
        'stratigraphic_layer': '地层归属',
        'time_span_start': '起始时间',
        'time_span_end': '结束时间',
        'absolute_dating': '绝对年代',
        'relative_dating': '相对年代',
        'development_stage': '发展阶段',
        'phase_sequence': '时期顺序',
        'characteristics': '时期特征',
        'representative_artifacts': '代表性文物'
    },
    'pottery_artifacts': {
        'id': 'ID',
        'artifact_code': '文物编号',
        'subtype': '器型',
        'clay_type': '陶土类型',
        'clay_purity': '纯洁度',
        'clay_fineness': '细腻度',
        'mixed_materials': '掺杂物',
        'color': '颜色',
        'hardness': '硬度',
        'firing_temperature': '烧成温度',
        'shape_features': '器型特征',
        'vessel_combination': '器物组合',
        'dimensions': '尺寸描述',
        'measurements': '量度信息',
        'height': '高度(cm)',
        'diameter': '口径(cm)',
        'thickness': '厚度(cm)',
        'function': '功能',
        'forming_technique': '成型工艺',
        'finishing_technique': '修整技术',
        'decoration_method': '装饰手法',
        'decoration_type': '纹饰类型',
        'production_activity': '制作活动',
        'maker': '制作者',
        'production_date': '制作年代',
        'production_location': '制作地点',
        'excavation_location': '原始出土地点',
        'ex_region': '出土区域',
        'ex_unit': '出土单位',
        'ex_layer': '出土层位',
        'location_site': '所在墓地/遗址',
        'found_in_tomb': '出土墓葬',
        'location_layer': '层位',
        'location_unit': '遗迹单位',
        'preservation_status': '保存状况',
        'completeness': '完整程度',
        'has_images': '有图片'
    },
    'jade_artifacts': {
        'id': 'ID',
        'artifact_code': '文物编号',
        'category_level1': '一级分类',
        'category_level2': '二级分类',
        'category_level3': '三级分类',
        'jade_type': '玉料类型',
        'jade_color': '玉料颜色',
        'jade_quality': '玉料质地',
        'surface_condition': '沁色/表面',
        'shape_unit': '器型单元',
        'overall_description': '整体形态',
        'decoration_unit': '纹饰单元',
        'decoration_theme': '纹饰主题',
        'craft_unit': '工艺单元',
        'cutting_technique': '切割工艺',
        'drilling_technique': '钻孔工艺',
        'carving_technique': '雕刻工艺',
        'dimensions': '尺寸描述',
        'measurements': '量度信息',
        'length': '长度(cm)',
        'width': '宽度(cm)',
        'thickness': '厚度(cm)',
        'height': '高度(cm)',
        'diameter': '直径(cm)',
        'hole_diameter': '孔径(cm)',
        'weight': '重量(g)',
        'function': '功能',
        'usage': '使用方式',
        'production_activity': '制作活动',
        'maker': '制作者',
        'production_date': '制作年代',
        'production_location': '制作地点',
        'excavation_location': '原始出土地点',
        'ex_region': '出土区域',
        'ex_unit': '出土单位',
        'ex_layer': '出土层位',
        'location_site': '所在墓地/遗址',
        'found_in_tomb': '出土墓葬',
        'location_layer': '层位',
        'location_unit': '遗迹单位',
        'preservation_status': '保存状况',
        'completeness': '完整程度',
        'has_images': '有图片'
    },
    'images': {
        'id': 'ID',
        'image_hash': '图片哈希',
        'image_path': '图片路径',
        'image_type': '图片类型',
        'page_idx': '页码',
        'caption': '说明',
        'width': '宽度',
        'height': '高度'
    },
    'sys_template_mappings': {
        'id': 'ID',
        'artifact_type': '文物类型',
        'field_name_cn': '抽取属性(CN)',
        'field_name_en': '数据库字段(EN)',
        'description': '字段说明',
        'cidoc_entity': 'Entity',
        'cidoc_property': 'Property',
        'target_class': 'Target Class'
    },
    'fact_artifact_triples': {
        'id': 'ID',
        'artifact_type': '文物类型',
        'artifact_id': '文物ID',
        'predicate': '关系谓词',
        'object_value': '属性值',
        'confidence': '置信度'
    }
}


def get_column_mapping(table_name: str) -> Dict[str, str]:
    """获取表的列名映射"""
    return COLUMN_MAPPINGS.get(table_name, {})
