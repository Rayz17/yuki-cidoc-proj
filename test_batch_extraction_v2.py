
import os
import sys
import json
import time

# Ensure project root is in sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from src.scheduler import BatchScheduler

def test_batch_extraction():
    print("🚀 Starting Batch Extraction Test (Concurrent)")
    
    # 1. Define paths
    report_folder = os.path.join(project_root, "遗址出土报告", "测试数据")
    templates_base = os.path.join(project_root, "抽取模版")
    
    # Check if paths exist
    if not os.path.exists(report_folder):
        print(f"❌ Report folder not found: {report_folder}")
        return
    if not os.path.exists(templates_base):
        print(f"❌ Templates folder not found: {templates_base}")
        return

    # 2. Define templates
    templates = {
        'site': os.path.join(templates_base, "数据结构3-遗址属性和类分析1129.xlsx"),
        'period': os.path.join(templates_base, "数据结构4-时期属性和类分析1129.xlsx"),
        'pottery': os.path.join(templates_base, "数据结构1-陶器文化特征单元分析1129.xlsx"),
        'jade': os.path.join(templates_base, "数据结构2-玉器文化特征单元分析1129.xlsx")
    }
    
    # Verify templates exist
    for k, v in templates.items():
        if not os.path.exists(v):
            print(f"❌ Template not found: {v}")
            return

    # 3. Create task configuration - SIMULATE 2 TASKS
    # We use the same folder but different report names to simulate concurrent tasks
    tasks = [
        {
            'report_folder': report_folder,
            'templates': templates,
            'report_name': 'Concurrent_Test_Task_A'
        },
        {
            'report_folder': report_folder,
            'templates': templates,
            'report_name': 'Concurrent_Test_Task_B'
        }
    ]
    
    # 4. Initialize Scheduler
    db_path = os.path.join(project_root, "database", "artifacts_v3.db")
    scheduler = BatchScheduler(db_path)
    
    if not scheduler.bot_pool:
        print("❌ Bot pool is empty! Check config.json")
        return
        
    print(f"✅ Loaded {len(scheduler.bot_pool)} bots from config")
    
    # 5. Execute with concurrency
    print(f"⏳ Executing batch of {len(tasks)} tasks with 2 workers...")
    start_time = time.time()
    
    # Set max_workers to 2 to test concurrency
    results = scheduler.execute_batch(tasks, max_workers=2) 
    
    end_time = time.time()
    print(f"⏱️ Total time: {end_time - start_time:.2f}s")

    # 6. Report
    print("\n📊 Execution Results:")
    for res in results:
        print(res)

if __name__ == "__main__":
    test_batch_extraction()
