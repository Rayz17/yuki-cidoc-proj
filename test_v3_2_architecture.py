"""
V3.2 架构集成测试脚本
验证元数据注册、实体插入和语义三元组生成
"""

import os
import sys
import json
from datetime import datetime

# 添加项目根目录到路径
sys.path.insert(0, os.path.abspath('.'))

from src.database_manager_v3 import DatabaseManagerV3
from src.template_analyzer import TemplateAnalyzer
from src.workflow import ExtractionWorkflow

def test_architecture():
    print("🚀 开始 V3.2 架构测试...\n")
    
    # 1. 设置测试环境
    db_path = 'database/test_v3_2.db'
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"🧹 清理旧数据库: {db_path}")
        
    # 2. 初始化数据库
    db = DatabaseManagerV3(db_path)
    db.connect()
    db.initialize_database()
    print("✅ 数据库初始化完成")
    
    # 3. 测试模版注册
    template_path = '抽取模版/数据结构1-陶器文化特征单元分析1129.xlsx'
    if not os.path.exists(template_path):
        print(f"❌ 找不到模版文件: {template_path}")
        return

    analyzer = TemplateAnalyzer(template_path)
    print(f"\n📚 读取模版: {template_path}")
    
    # 获取定义并注册
    mappings = analyzer.get_template_definitions('pottery')
    db.register_template_mappings(mappings)
    print(f"✅ 注册了 {len(mappings)} 个字段映射")
    
    # 验证注册结果
    cursor = db.conn.cursor()
    cursor.execute("SELECT count(*) FROM sys_template_mappings WHERE artifact_type='pottery'")
    count = cursor.fetchone()[0]
    print(f"📊 数据库中查询到 {count} 条映射记录")
    assert count > 0, "模版映射注册失败"
    
    # 4. 模拟写入 Artifact 和 Triples
    # 这里我们不运行完整的 workflow (因为它需要 LLM API)，而是手动调用 db 方法来模拟 workflow 的最后一步
    
    print("\n💾 模拟写入文物和三元组...")
    
    # 获取 mapping IDs
    mapping_ids = db.get_template_mapping_ids('pottery')
    
    # 模拟一个抽取到的文物数据
    mock_artifact = {
        'task_id': 'test_task_001',
        'artifact_code': 'M1:1',
        'artifact_type': 'pottery',
        'subtype': '陶罐',
        'clay_type': '夹砂红陶', # 这是一个映射字段
        'height': 15.5,
        'raw_attributes': '{"陶土种类": "夹砂红陶", "器高": 15.5}',
        'cidoc_attributes': '{}'
    }
    
    # 插入文物
    # 注意：我们需要先创建一个 dummy task 和 site，否则外键约束可能会失败（取决于 SQLite 设置，通常默认不强制，但 schema 里有）
    db.create_task({
        'task_id': 'test_task_001', 
        'report_name': 'Test Report', 
        'report_folder_path': '/tmp'
    })
    
    # 插入陶器
    artifact_id = db.insert_pottery(mock_artifact)
    print(f"✅ 插入文物 ID: {artifact_id}")
    
    # 构造三元组
    # 假设 '陶土种类' 对应 mock_artifact 中的 'clay_type' 值
    # 我们需要找到 '陶土种类' 在 mapping_ids 中的 ID
    clay_mapping_id = mapping_ids.get('陶土种类')
    
    if clay_mapping_id:
        triples = [{
            'artifact_type': 'pottery',
            'artifact_id': artifact_id,
            'mapping_id': clay_mapping_id,
            'predicate': 'P45_consists_of', # 假设的谓词
            'object_value': '夹砂红陶',
            'confidence': 0.95
        }]
        
        db.insert_fact_triples(triples)
        print(f"✅ 插入 {len(triples)} 条语义三元组")
        
        # 验证三元组写入
        cursor.execute("SELECT * FROM fact_artifact_triples WHERE artifact_id=?", (artifact_id,))
        rows = cursor.fetchall()
        print(f"📊 数据库中查询到 {len(rows)} 条三元组记录")
        for row in rows:
            print(f"   - ID: {row['id']}, Value: {row['object_value']}, Predicate: {row['predicate']}")
        
        assert len(rows) == 1, "三元组写入失败"
    else:
        print("⚠️ 警告：在模版映射中未找到 '陶土种类'，跳过三元组测试")

    db.close()
    print("\n✨ V3.2 架构测试全部通过！")

if __name__ == "__main__":
    test_architecture()

