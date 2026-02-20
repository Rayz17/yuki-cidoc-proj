from src.db.database import SessionLocal
from src.services.agent_manager import AgentManager
from src.db.models import AgentConfig

def test_list_agents():
    db = SessionLocal()
    try:
        manager = AgentManager(db)
        agents = manager.list_agents()
        print(f"Found {len(agents)} agents.")
        for agent in agents:
            print(f"Agent: {agent.name}, Base URL: {agent.api_base_url}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    test_list_agents()
