from src.db.database import SessionLocal
from src.db.models import AgentConfig

def cleanup_agents():
    db = SessionLocal()
    try:
        # Delete empty agents
        db.query(AgentConfig).filter(AgentConfig.name == "").delete()
        db.query(AgentConfig).filter(AgentConfig.name == None).delete()
        db.commit()
        print("Cleanup complete.")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    cleanup_agents()
