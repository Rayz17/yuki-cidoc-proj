import asyncio
import json
from unittest.mock import AsyncMock, patch, MagicMock
from src.db.database import SessionLocal, engine, Base
from src.db.models import SysTask
from src.services.orchestrator import Orchestrator
from src.services.merger_service import MergerService
import uuid

# 1. Setup DB
Base.metadata.create_all(bind=engine)
db = SessionLocal()

async def run_test():
    print("--- Starting E2E Logic Test ---")
    
    # 2. Mock Coze
    agent_a_resp = {
        "global_tips": "Units: cm",
        "entities": [
            {
                "type": "SITE",
                "name": "TestSite_Alpha",
                "children": [
                    {
                        "type": "POTTERY",
                        "name": "P1",
                        "related_text": "A pottery jar."
                    }
                ]
            }
        ]
    }
    
    agent_b_resp = {
        "PSD1": {"value": "Intact", "quote": "Intact"},
        "Dimensions": {"value": "15", "quote": "Height 15"}
    }
    
    with patch("src.services.orchestrator.coze_client") as mock_coze:
        async def mock_chat(bot_id, user_id, query):
            if "Analyze this text" in query:
                return {"messages": [{"content": json.dumps(agent_a_resp)}]}
            else:
                return {"messages": [{"content": json.dumps(agent_b_resp)}]}
        
        mock_coze.chat = AsyncMock(side_effect=mock_chat)
        
        # 3. Create Task
        task_id = str(uuid.uuid4())
        task = SysTask(id=task_id, file_path="dummy.txt", status="PENDING")
        db.add(task)
        db.commit()
        
        print(f"Task Created: {task_id}")
        
        # 4. Run Orchestrator
        orch = Orchestrator(db)
        await orch.process_task(task_id, "Raw content of report...")
        
        print("Orchestrator Finished.")
        
        # 5. Verify Extraction
        task = db.query(SysTask).get(task_id)
        print(f"Task Status: {task.status}")
        assert task.status == "COMPLETED"
        assert task.global_context_tips == "Units: cm"
        
        # 6. Run Merger
        print("Running Merger...")
        merger = MergerService(db)
        res = merger.merge_task(task_id)
        
        print(f"Merge Result: {res}")
        assert res['merged_entities'] > 0
        assert res['site_name'] == "TestSite_Alpha"
        
        print("--- Test Passed Successfully ---")

if __name__ == "__main__":
    asyncio.run(run_test())
