import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, UniqueConstraint, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from src.db.database import Base
from sqlalchemy.types import TypeDecorator, CHAR

# Helper for UUID in SQLite (since SQLite doesn't support UUID natively)
class GUID(TypeDecorator):
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(UUID())
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == 'postgresql':
            return str(value)
        else:
            if not isinstance(value, uuid.UUID):
                return str(uuid.UUID(value))
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        else:
            if not isinstance(value, uuid.UUID):
                return uuid.UUID(value)
            return value

class SysTask(Base):
    __tablename__ = "sys_tasks"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    file_path = Column(String(255), nullable=False) # Main file or first file
    status = Column(String(50), default="PENDING") # PENDING, STRUCTURING, EXTRACTING, COMPLETED, FAILED, CANCELLED, SUSPENDED
    
    # [新增] 全局上下文/小抄
    global_context_tips = Column(Text, nullable=True)
    
    # [New V3.3 Fields]
    bot_structure_id = Column(String(100), nullable=True) # Assigned Structure Bot ID
    bot_extraction_id = Column(String(100), nullable=True) # Assigned Extraction Bot ID
    llm_model_info = Column(Text, nullable=True) # JSON: {structure: "model_a", extraction: "model_b"}
    target_files = Column(Text, nullable=True) # JSON: List of filenames for multi-file tasks
    progress = Column(Text, nullable=True) # JSON: {"phase": "STRUCTURE", "chunk_index": 10}
    
    start_time = Column(DateTime, nullable=True)
    end_time = Column(DateTime, nullable=True)
    is_paused = Column(Boolean, default=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Entity(Base):
    __tablename__ = "entities"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    parent_id = Column(GUID(), ForeignKey("entities.id"), nullable=True)
    root_id = Column(GUID(), ForeignKey("entities.id"), nullable=True) # Usually the Site or the Task root
    task_id = Column(GUID(), ForeignKey("sys_tasks.id"), nullable=True) # Link to source task
    
    entity_type = Column(String(50), nullable=False) # SITE, SUBAREA, FEATURE, POTTERY, JADE
    name = Column(String(255), nullable=False)
    
    # [新增] 实体级备注/小抄
    entity_specific_tips = Column(Text, nullable=True)
    
    extraction_status = Column(String(50), default="PENDING") # PENDING, EXTRACTED
    
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    # Fix self-referential relationship
    children = relationship("Entity", 
                          back_populates="parent",
                          foreign_keys=[parent_id])
                          
    parent = relationship("Entity", 
                        remote_side=[id],
                        back_populates="children",
                        foreign_keys=[parent_id])
                        
    attributes = relationship("EntityAttribute", back_populates="entity")
    segments = relationship("TextSegment", back_populates="entity")

    __table_args__ = (
        UniqueConstraint('parent_id', 'entity_type', 'name', 'task_id', name='uq_entity_in_context'),
    )

class TextSegment(Base):
    __tablename__ = "text_segments"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    entity_id = Column(GUID(), ForeignKey("entities.id"), nullable=False)
    
    content = Column(Text, nullable=False)
    source_location = Column(String(255), nullable=True) # Page number, section, etc.
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    entity = relationship("Entity", back_populates="segments")

class EntityAttribute(Base):
    __tablename__ = "entity_attributes"

    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    entity_id = Column(GUID(), ForeignKey("entities.id"), nullable=False)
    
    attribute_code = Column(String(255), nullable=False) # e.g. ProductionDate.C2.cultural_period
    attribute_value = Column(Text, nullable=True) # The extracted code/value
    quote = Column(Text, nullable=True) # Quote/Evidence
    
    confidence = Column(String(20), nullable=True) # HIGH, MEDIUM, LOW
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    entity = relationship("Entity", back_populates="attributes")

# --- Master Data Layer ---

class MasterEntity(Base):
    __tablename__ = "master_entities"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    
    # Logical Grouping
    site_name = Column(String(255), nullable=False, default="Unknown") 
    
    entity_type = Column(String(50), nullable=False)
    name = Column(String(255), nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    attributes = relationship("MasterAttribute", back_populates="master_entity")

    __table_args__ = (
        UniqueConstraint('site_name', 'entity_type', 'name', name='uq_master_entity'),
    )

class MasterAttribute(Base):
    __tablename__ = "master_attributes"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    master_entity_id = Column(GUID(), ForeignKey("master_entities.id"), nullable=False)
    
    attribute_code = Column(String(255), nullable=False)
    attribute_value = Column(Text, nullable=True)
    quote = Column(Text, nullable=True) # Quote/Evidence
    
    # Lineage: Where did this data come from?
    source_task_id = Column(GUID(), ForeignKey("sys_tasks.id"), nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    master_entity = relationship("MasterEntity", back_populates="attributes")

# --- Agent Management Layer ---

class AgentConfig(Base):
    __tablename__ = "agent_configs"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    
    name = Column(String(100), nullable=False)
    bot_id = Column(String(100), nullable=False, unique=True)
    agent_type = Column(String(50), nullable=False) # STRUCTURE (A), EXTRACTION (B), DEDUP (C)
    api_token = Column(String(255), nullable=True) # Optional override token
    api_base_url = Column(String(255), nullable=True) # Optional override base URL
    
    is_active = Column(Integer, default=1) # 1=Active, 0=Inactive
    
    # [New V3.3 Fields]
    locked_by_task_id = Column(String(100), nullable=True) # Task ID that currently owns this bot
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# --- System Settings Layer ---

class SystemSetting(Base):
    __tablename__ = "system_settings"
    
    id = Column(GUID(), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), nullable=False, unique=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
