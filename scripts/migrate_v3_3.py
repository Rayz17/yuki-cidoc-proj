import sys
import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings

def migrate():
    print("Starting migration to V3.3...")
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # 1. Update sys_tasks table
        print("Migrating sys_tasks...")
        try:
            conn.execute(text("ALTER TABLE sys_tasks ADD COLUMN bot_structure_id VARCHAR(100)"))
            print("- Added bot_structure_id")
        except Exception as e:
            print(f"- Skipped bot_structure_id: {e}")

        try:
            conn.execute(text("ALTER TABLE sys_tasks ADD COLUMN bot_extraction_id VARCHAR(100)"))
            print("- Added bot_extraction_id")
        except Exception as e:
            print(f"- Skipped bot_extraction_id: {e}")

        try:
            conn.execute(text("ALTER TABLE sys_tasks ADD COLUMN llm_model_info TEXT"))
            print("- Added llm_model_info")
        except Exception as e:
            print(f"- Skipped llm_model_info: {e}")

        try:
            conn.execute(text("ALTER TABLE sys_tasks ADD COLUMN target_files TEXT"))
            print("- Added target_files")
        except Exception as e:
            print(f"- Skipped target_files: {e}")

        try:
            conn.execute(text("ALTER TABLE sys_tasks ADD COLUMN start_time DATETIME"))
            print("- Added start_time")
        except Exception as e:
            print(f"- Skipped start_time: {e}")

        try:
            conn.execute(text("ALTER TABLE sys_tasks ADD COLUMN end_time DATETIME"))
            print("- Added end_time")
        except Exception as e:
            print(f"- Skipped end_time: {e}")

        try:
            conn.execute(text("ALTER TABLE sys_tasks ADD COLUMN is_paused BOOLEAN DEFAULT 0"))
            print("- Added is_paused")
        except Exception as e:
            print(f"- Skipped is_paused: {e}")

        # 2. Update agent_configs table
        print("Migrating agent_configs...")
        try:
            conn.execute(text("ALTER TABLE agent_configs ADD COLUMN locked_by_task_id VARCHAR(100)"))
            print("- Added locked_by_task_id")
        except Exception as e:
            print(f"- Skipped locked_by_task_id: {e}")
            
        conn.commit()
    
    print("Migration V3.3 complete.")

if __name__ == "__main__":
    migrate()
