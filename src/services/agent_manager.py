from sqlalchemy.orm import Session
from sqlalchemy import or_
from src.db.models import AgentConfig
import random
import uuid

class AgentManager:
    def __init__(self, db: Session):
        self.db = db

    def create_agent(self, name: str, bot_id: str, agent_type: str, api_token: str = None, api_base_url: str = None) -> AgentConfig:
        """Create a new agent configuration."""
        agent = AgentConfig(
            name=name,
            bot_id=bot_id,
            agent_type=agent_type.upper(),
            api_token=api_token,
            api_base_url=api_base_url
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def get_agent(self, agent_id: str) -> AgentConfig:
        """Get agent by ID."""
        return self.db.query(AgentConfig).filter(AgentConfig.id == agent_id).first()

    def list_agents(self, agent_type: str = None) -> list[AgentConfig]:
        """List all agents, optionally filtered by type."""
        query = self.db.query(AgentConfig)
        if agent_type:
            query = query.filter(AgentConfig.agent_type == agent_type.upper())
        return query.all()

    def update_agent(self, agent_id: str, **kwargs) -> AgentConfig:
        """Update agent details."""
        agent = self.get_agent(agent_id)
        if not agent:
            raise ValueError("Agent not found")
        
        for key, value in kwargs.items():
            if hasattr(agent, key):
                setattr(agent, key, value)
        
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def delete_agent(self, agent_id: str):
        """Delete an agent."""
        agent = self.get_agent(agent_id)
        if agent:
            self.db.delete(agent)
            self.db.commit()

    def get_next_agent(self, agent_type: str) -> AgentConfig:
        """
        Get the next available agent for a task (Load Balancing).
        Currently implements Random strategy.
        """
        agents = self.db.query(AgentConfig).filter(
            AgentConfig.agent_type == agent_type.upper(),
            AgentConfig.is_active == 1
        ).all()
        
        if not agents:
            return None
            
        return random.choice(agents)

    def allocate_bot_pair(self, task_id: str) -> dict:
        """
        Finds and locks one idle Structure bot and one idle Extraction bot.
        Returns a dict with 'structure' and 'extraction' AgentConfig objects.
        Raises ValueError if resources are insufficient.
        """
        # 1. Find idle Structure Bot
        # Use Optimistic Locking instead of DB locking to avoid SQLite issues
        candidates_s = self.db.query(AgentConfig).filter(
            AgentConfig.agent_type == "STRUCTURE",
            AgentConfig.is_active == 1,
            or_(AgentConfig.locked_by_task_id == None, AgentConfig.locked_by_task_id == "")
        ).all()

        structure_agent = None
        for cand in candidates_s:
            # Try to lock it atomically
            rows = self.db.query(AgentConfig).filter(
                AgentConfig.id == cand.id,
                or_(AgentConfig.locked_by_task_id == None, AgentConfig.locked_by_task_id == "")
            ).update({"locked_by_task_id": str(task_id)})
            
            if rows > 0:
                self.db.commit()
                structure_agent = cand
                break

        if not structure_agent:
            # Check if there are ANY structure bots
            any_structure = self.db.query(AgentConfig).filter(AgentConfig.agent_type == "STRUCTURE").count()
            if any_structure == 0:
                raise ValueError("No Structure Bots configured in the system.")
            else:
                raise ValueError("All Structure Bots are currently busy.")

        # 2. Find idle Extraction Bot
        candidates_e = self.db.query(AgentConfig).filter(
            AgentConfig.agent_type == "EXTRACTION",
            AgentConfig.is_active == 1,
            or_(AgentConfig.locked_by_task_id == None, AgentConfig.locked_by_task_id == "")
        ).all()

        extraction_agent = None
        for cand in candidates_e:
            rows = self.db.query(AgentConfig).filter(
                AgentConfig.id == cand.id,
                or_(AgentConfig.locked_by_task_id == None, AgentConfig.locked_by_task_id == "")
            ).update({"locked_by_task_id": str(task_id)})
            
            if rows > 0:
                self.db.commit()
                extraction_agent = cand
                break

        if not extraction_agent:
            # Rollback Structure Bot lock if we failed to get Extraction Bot
            if structure_agent:
                structure_agent.locked_by_task_id = None
                self.db.commit()
                
            # Check if there are ANY extraction bots
            any_extraction = self.db.query(AgentConfig).filter(AgentConfig.agent_type == "EXTRACTION").count()
            if any_extraction == 0:
                raise ValueError("No Extraction Bots configured in the system.")
            else:
                raise ValueError("All Extraction Bots are currently busy.")

        return {
            "structure": structure_agent,
            "extraction": extraction_agent
        }

    def release_bot_pair(self, task_id: str):
        """
        Releases any bots locked by the given task_id.
        Triggers queue processing for the next task.
        """
        agents = self.db.query(AgentConfig).filter(
            AgentConfig.locked_by_task_id == str(task_id)
        ).all()

        if not agents:
            return

        for agent in agents:
            agent.locked_by_task_id = None
        
        self.db.commit()

        # Check queue immediately after releasing resources
        # We need to import here to avoid circular dependency
        from src.api.tasks import check_queue_and_start_next
        try:
            check_queue_and_start_next(self.db)
        except Exception as e:
            print(f"Error triggering queued task: {e}")
