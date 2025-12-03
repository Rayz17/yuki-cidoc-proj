"""
多任务并行调度器
负责管理Bot资源池和并发执行抽取任务
"""

import concurrent.futures
import time
import json
import os
from typing import List, Dict, Optional
from src.workflow import ExtractionWorkflow

class BatchScheduler:
    def __init__(self, db_path: str = 'database/artifacts_v3.db'):
        self.db_path = db_path
        # 从配置文件加载 Bot 资源池
        self.bot_pool = self._load_bot_pool()
        
    def _load_bot_pool(self) -> List[Dict]:
        """加载 Bot 配置"""
        try:
            config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'config.json')
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('llm', {}).get('bot_pool', [])
        except Exception as e:
            print(f"⚠️ 无法加载配置文件中的 Bot Pool: {e}")
            return []

    def execute_batch(self, tasks: List[Dict], max_workers: int = 5):
        """
        执行批量任务
        
        Args:
            tasks: 任务列表
            max_workers: 最大并发数
        """
        results = []
        
        if not self.bot_pool:
            return [{'name': 'Error', 'status': 'failed', 'error': '没有可用的 Bot 配置'}]
        
        # 限制并发数不超过 Bot 数量
        actual_workers = min(max_workers, len(self.bot_pool))
        if actual_workers < 1:
            actual_workers = 1
            
        print(f"🚀 开始批量执行 {len(tasks)} 个任务，并发数: {actual_workers}")
        
        # 预先创建所有任务，以便在GUI中显示等待状态
        pending_tasks = []
        temp_workflow = ExtractionWorkflow(self.db_path)
        try:
            for task in tasks:
                # 创建任务并获取 task_id
                task_id = temp_workflow.create_task(
                    task['report_folder'], 
                    task['report_name']
                )
                # 更新 task 对象，加入 task_id
                task_with_id = task.copy()
                task_with_id['task_id'] = task_id
                pending_tasks.append(task_with_id)
                print(f"📋 任务已创建: {task['report_name']} (ID: {task_id}) - 等待执行")
        except Exception as e:
            print(f"❌ 创建任务失败: {e}")
            temp_workflow.close()
            return [{'name': 'Error', 'status': 'failed', 'error': f'任务创建失败: {e}'}]
        finally:
            temp_workflow.close()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=actual_workers) as executor:
            # 提交所有任务
            future_to_task = {}
            
            for i, task in enumerate(pending_tasks):
                # 分配 Bot (简单的轮询分配)
                bot_config = self.bot_pool[i % len(self.bot_pool)]
                
                future = executor.submit(
                    self._run_single_task, 
                    task, 
                    bot_config
                )
                future_to_task[future] = task['report_name']
            
            # 等待结果
            for future in concurrent.futures.as_completed(future_to_task):
                name = future_to_task[future]
                try:
                    task_id = future.result()
                    results.append({'name': name, 'status': 'success', 'task_id': task_id})
                    print(f"✅ 任务完成: {name}")
                except Exception as e:
                    results.append({'name': name, 'status': 'failed', 'error': str(e)})
                    print(f"❌ 任务失败: {name} - {str(e)}")
                    
        return results

    def _run_single_task(self, task_config: Dict, bot_config: Dict) -> str:
        """运行单个任务"""
        workflow = ExtractionWorkflow(self.db_path)
        bot_id = bot_config.get('bot_id')
        api_key = bot_config.get('api_key')
        task_id = task_config.get('task_id')
        
        try:
            print(f"▶️ 启动任务: {task_config['report_name']} (Bot: {bot_config.get('name', bot_id)})")
            
            task_id = workflow.execute_full_extraction(
                report_folder=task_config['report_folder'],
                templates=task_config['templates'],
                report_name=task_config['report_name'],
                bot_id=bot_id,
                api_key=api_key,
                task_id=task_id  # 传入预先创建的 task_id
            )
            return task_id
        finally:
            workflow.close()

