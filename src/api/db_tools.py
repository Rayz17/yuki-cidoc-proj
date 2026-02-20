from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect
from src.db.database import get_db, engine
from src.db.models import MasterEntity, MasterAttribute, SystemSetting
from pydantic import BaseModel
from typing import List, Dict, Any
import json
import os
from datetime import datetime

router = APIRouter()

BACKUP_DIR = "backups"
os.makedirs(BACKUP_DIR, exist_ok=True)

class SqlQuery(BaseModel):
    query: str

class SettingUpdate(BaseModel):
    key: str
    value: str
    description: str = None

@router.get("/schema", response_model=Dict[str, List[Dict[str, str]]])
def get_db_schema():
    """Get database schema (tables and columns)."""
    inspector = inspect(engine)
    schema = {}
    for table_name in inspector.get_table_names():
        columns = []
        for column in inspector.get_columns(table_name):
            columns.append({
                "name": column['name'],
                "type": str(column['type'])
            })
        schema[table_name] = columns
    return schema

@router.get("/preview/{table_name}")
def preview_table(table_name: str, db: Session = Depends(get_db)):
    """Get first 10 rows of a table."""
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        raise HTTPException(status_code=404, detail="Table not found")
    
    try:
        query = text(f"SELECT * FROM {table_name} LIMIT 10")
        result = db.execute(query)
        keys = result.keys()
        data = [dict(zip(keys, row)) for row in result.fetchall()]
        return {"columns": list(keys), "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/query")
def execute_query(query: SqlQuery, db: Session = Depends(get_db)):
    """Execute a read-only SQL query."""
    sql = query.query.strip().lower()
    if not sql.startswith("select"):
        raise HTTPException(status_code=400, detail="Only SELECT queries are allowed.")
    
    try:
        result = db.execute(text(query.query))
        keys = result.keys()
        data = [dict(zip(keys, row)) for row in result.fetchall()]
        return {"columns": list(keys), "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/reset")
def reset_database():
    """Reset the database (Drop all tables and recreate)."""
    from src.db.database import Base
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        return {"status": "success", "message": "Database reset successfully."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Snapshots (Backup/Restore) ---

@router.get("/snapshots", response_model=List[str])
def list_snapshots():
    """List available snapshot files."""
    try:
        files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".json")]
        files.sort(reverse=True) # Newest first
        return files
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/snapshots")
def create_snapshot(db: Session = Depends(get_db)):
    """Create a new snapshot of Master Data."""
    try:
        # 1. Fetch Data
        entities = db.query(MasterEntity).all()
        data = []
        for entity in entities:
            attrs = db.query(MasterAttribute).filter(MasterAttribute.master_entity_id == entity.id).all()
            attr_list = []
            for attr in attrs:
                attr_list.append({
                    "code": attr.attribute_code,
                    "value": attr.attribute_value,
                    "quote": attr.original_text,
                    "source_task_id": str(attr.source_task_id) if attr.source_task_id else None
                })
            
            data.append({
                "site_name": entity.site_name,
                "type": entity.entity_type,
                "name": entity.name,
                "attributes": attr_list
            })
            
        # 2. Write to File
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"snapshot_{timestamp}.json"
        filepath = os.path.join(BACKUP_DIR, filename)
        
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            
        return {"status": "success", "filename": filename, "count": len(data)}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/snapshots/{filename}")
def get_snapshot_content(filename: str):
    """Read snapshot content."""
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Snapshot not found")
        
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/snapshots/restore/{filename}")
def restore_snapshot(filename: str, db: Session = Depends(get_db)):
    """Restore Master Data from snapshot (Overwrites existing)."""
    filepath = os.path.join(BACKUP_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Snapshot not found")
        
    try:
        # 1. Read Data
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        # 2. Clear Tables
        db.query(MasterAttribute).delete()
        db.query(MasterEntity).delete()
        db.flush()
        
        # 3. Insert Data
        count = 0
        for item in data:
            entity = MasterEntity(
                site_name=item["site_name"],
                entity_type=item["type"],
                name=item["name"]
            )
            db.add(entity)
            db.flush() # Get ID
            
            for attr in item["attributes"]:
                ma = MasterAttribute(
                    master_entity_id=entity.id,
                    attribute_code=attr["code"],
                    attribute_value=attr["value"],
                    original_text=attr["quote"],
                    source_task_id=attr.get("source_task_id") # Might be None if from older snapshot
                )
                db.add(ma)
            count += 1
            
        db.commit()
        return {"status": "success", "restored_count": count}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

# --- Settings API ---

@router.get("/settings", response_model=List[dict])
def list_settings(db: Session = Depends(get_db)):
    """List all system settings."""
    settings = db.query(SystemSetting).all()
    return [{"key": s.key, "value": s.value, "description": s.description} for s in settings]

@router.post("/settings")
def update_setting(setting: SettingUpdate, db: Session = Depends(get_db)):
    """Update or create a setting."""
    s = db.query(SystemSetting).filter(SystemSetting.key == setting.key).first()
    if s:
        s.value = setting.value
        if setting.description:
            s.description = setting.description
    else:
        s = SystemSetting(
            key=setting.key,
            value=setting.value,
            description=setting.description
        )
        db.add(s)
    
    db.commit()
    return {"status": "success", "key": s.key, "value": s.value}
