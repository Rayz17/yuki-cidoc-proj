"""
GUI V3.0 功能测试脚本
"""

import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gui.db_helper import DatabaseHelper

def test_db_helper():
    """测试数据库辅助类"""
    print("=" * 60)
    print("测试数据库辅助类")
    print("=" * 60)
    
    db_path = "database/artifacts_v3.db"
    
    if not os.path.exists(db_path):
        print(f"⚠️  数据库不存在: {db_path}")
        print("请先运行: python src/main_v3.py --init-db ...")
        return False
    
    db = DatabaseHelper(db_path)
    
    # 测试统计功能
    print("\n1. 测试统计功能...")
    try:
        stats = db.get_statistics()
        print(f"   ✅ 任务数: {stats['task_count']}")
        print(f"   ✅ 遗址数: {stats['site_count']}")
        print(f"   ✅ 陶器数: {stats['pottery_count']}")
        print(f"   ✅ 玉器数: {stats['jade_count']}")
        print(f"   ✅ 图片数: {stats['image_count']}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    # 测试任务列表
    print("\n2. 测试任务列表...")
    try:
        tasks = db.get_all_tasks()
        print(f"   ✅ 获取到 {len(tasks)} 个任务")
        if tasks:
            print(f"   最新任务: {tasks[0]['task_id']}")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    # 测试表列表
    print("\n3. 测试表列表...")
    try:
        tables = db.get_table_list()
        print(f"   ✅ 数据库有 {len(tables)} 个表")
        print(f"   表名: {', '.join(tables[:5])}...")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    # 测试文物查询
    print("\n4. 测试文物查询...")
    try:
        pottery, total = db.get_artifacts('pottery', limit=5)
        print(f"   ✅ 陶器总数: {total}, 获取前5件")
        
        jade, total = db.get_artifacts('jade', limit=5)
        print(f"   ✅ 玉器总数: {total}, 获取前5件")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有测试通过！")
    print("=" * 60)
    return True


def test_imports():
    """测试导入"""
    print("=" * 60)
    print("测试模块导入")
    print("=" * 60)
    
    try:
        print("\n1. 测试 db_helper 导入...")
        from gui.db_helper import DatabaseHelper, get_column_mapping
        print("   ✅ db_helper 导入成功")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    try:
        print("\n2. 测试 workflow 导入...")
        from src.workflow import ExtractionWorkflow
        print("   ✅ workflow 导入成功")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    try:
        print("\n3. 测试 database_manager_v3 导入...")
        from src.database_manager_v3 import DatabaseManagerV3
        print("   ✅ database_manager_v3 导入成功")
    except Exception as e:
        print(f"   ❌ 失败: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("✅ 所有导入测试通过！")
    print("=" * 60)
    return True


def main():
    """主测试函数"""
    print("\n🧪 GUI V3.0 功能测试\n")
    
    # 测试导入
    if not test_imports():
        print("\n❌ 导入测试失败，请检查代码")
        return 1
    
    # 测试数据库辅助类
    if not test_db_helper():
        print("\n⚠️  数据库测试失败（可能是数据库未初始化）")
        print("   建议先运行一次抽取任务")
    
    print("\n" + "=" * 60)
    print("🎉 测试完成！")
    print("=" * 60)
    print("\n下一步:")
    print("  1. 启动GUI: streamlit run gui/app_v3.py")
    print("  2. 在浏览器中访问: http://localhost:8501")
    print("  3. 尝试执行一次抽取任务")
    print("\n")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

