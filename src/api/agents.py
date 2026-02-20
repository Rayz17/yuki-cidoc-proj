from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from src.db.database import get_db
from src.services.agent_manager import AgentManager
from pydantic import BaseModel, ConfigDict
from typing import Optional, List
from uuid import UUID

router = APIRouter()

class AgentCreate(BaseModel):
    name: str
    bot_id: str
    agent_type: str
    api_token: Optional[str] = None
    api_base_url: Optional[str] = None

class AgentUpdate(BaseModel):
    name: Optional[str] = None
    bot_id: Optional[str] = None
    agent_type: Optional[str] = None
    api_token: Optional[str] = None
    api_base_url: Optional[str] = None
    is_active: Optional[int] = None

class AgentOut(BaseModel):
    id: UUID
    name: str
    bot_id: str
    agent_type: str
    api_base_url: Optional[str] = None
    is_active: int
    locked_by_task_id: Optional[str] = None
    
    model_config = ConfigDict(from_attributes=True)

@router.post("/", response_model=AgentOut)
def create_agent(agent: AgentCreate, db: Session = Depends(get_db)):
    manager = AgentManager(db)
    try:
        return manager.create_agent(
            name=agent.name,
            bot_id=agent.bot_id,
            agent_type=agent.agent_type,
            api_token=agent.api_token,
            api_base_url=agent.api_base_url
        )
    except IntegrityError:
        raise HTTPException(status_code=409, detail=f"Agent with Bot ID '{agent.bot_id}' already exists.")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/", response_model=List[AgentOut])
def list_agents(type: Optional[str] = None, db: Session = Depends(get_db)):
    manager = AgentManager(db)
    return manager.list_agents(agent_type=type)

@router.put("/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: str, agent: AgentUpdate, db: Session = Depends(get_db)):
    manager = AgentManager(db)
    try:
        return manager.update_agent(agent_id, **agent.model_dump(exclude_unset=True))
    except ValueError:
        raise HTTPException(status_code=404, detail="Agent not found")
    except IntegrityError:
        raise HTTPException(status_code=409, detail="Bot ID already in use by another agent.")

@router.delete("/{agent_id}")
def delete_agent(agent_id: str, db: Session = Depends(get_db)):
    manager = AgentManager(db)
    manager.delete_agent(agent_id)
    return {"status": "success"}
