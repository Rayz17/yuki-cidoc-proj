from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from src.db.database import get_db
from src.db.models import SysTask, Entity, EntityAttribute, TextSegment
from src.services.orchestrator import Orchestrator
from src.services.merger_service import MergerService
from src.services.agent_manager import AgentManager
import uuid
import shutil
import os
import json
import csv
import io
from typing import List, Optional

router = APIRouter()

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

def generate_task_csv_stream(task_id: str, db: Session):
    """Generator for streaming task CSV export."""
    output = io.StringIO()
    # Define columns
    fieldnames = ["Entity ID", "Parent ID", "Name", "Type", "Tips", "Source Text", "Attribute Code", "Attribute Value", "Quote", "Confidence"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    # Yield header
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)
    
    batch_size = 1000
    offset = 0
    
    while True:
        # Fetch batch of entities with attributes and segments eagerly loaded
        entities = db.query(Entity)\
            .options(joinedload(Entity.attributes), joinedload(Entity.segments))\
            .filter(Entity.task_id == task_id)\
            .order_by(Entity.id)\
            .offset(offset).limit(batch_size).all()
            
        if not entities:
            break
            
        for entity in entities:
            # Base entity info
            base_row = {
                "Entity ID": str(entity.id),
                "Parent ID": str(entity.parent_id) if entity.parent_id else "",
                "Name": entity.name,
                "Type": entity.entity_type,
                "Tips": entity.entity_specific_tips or "",
                "Source Text": ""
            }
            
            # Get Source Text from segments
            if entity.segments:
                 base_row["Source Text"] = "\n".join([s.content for s in entity.segments])

            # Get attributes (already loaded)
            attributes = entity.attributes
            
            if not attributes:
                # Just the entity row
                row = base_row.copy()
                # Empty attribute fields
                row["Attribute Code"] = ""
                row["Attribute Value"] = ""
                row["Quote"] = ""
                row["Confidence"] = ""
                writer.writerow(row)
            else:
                for attr in attributes:
                    row = base_row.copy()
                    row["Attribute Code"] = attr.attribute_code
                    row["Attribute Value"] = attr.attribute_value
                    row["Quote"] = attr.quote
                    row["Confidence"] = attr.confidence
                    writer.writerow(row)
        
        # Yield batch
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        offset += batch_size

@router.get("/{task_id}/export")
def export_task_csv(task_id: str, db: Session = Depends(get_db)):
    """
    Export all task details (entities and attributes) to CSV via Stream.
    """
    task = db.query(SysTask).filter(SysTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return StreamingResponse(
        generate_task_csv_stream(task_id, db),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=task_{task_id}_export.csv"}
    )

@router.post("/{task_id}/merge", response_model=dict)
async def merge_task(task_id: str, db: Session = Depends(get_db)):
    """
    Merge the results of a specific task into the Master Data Layer.
    Allows merging for COMPLETED or STOPPED tasks.
    """
    task = db.query(SysTask).filter(SysTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    if task.status not in ["COMPLETED", "STOPPED"]:
        raise HTTPException(status_code=400, detail="Only COMPLETED or STOPPED tasks can be merged.")

    merger = MergerService(db)
    try:
        result = await merger.merge_task(task_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Log the full error for debugging
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")

@router.post("/{task_id}/pause")
def pause_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(SysTask).filter(SysTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    if task.status not in ["STRUCTURING", "EXTRACTING"]:
         raise HTTPException(status_code=400, detail="Task is not running.")
         
    task.is_paused = True
    db.commit()
    return {"status": "paused"}

@router.post("/{task_id}/resume")
def resume_task(task_id: str, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    task = db.query(SysTask).filter(SysTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
        
    # If SUSPENDED, we need to relaunch the background task
    if task.status == "SUSPENDED":
        agent_manager = AgentManager(db)
        try:
            # 1. Force Release existing bots (to fix double booking)
            agent_manager.release_bot_pair(str(task.id))
            
            # 2. Try to grab resources again
            bot_pair = agent_manager.allocate_bot_pair(str(task.id))
            # Update task with new bot IDs
            task.bot_structure_id = str(bot_pair["structure"].id)
            task.bot_extraction_id = str(bot_pair["extraction"].id)
            
            # Smart Resume Status Logic
            # If we have progress indicating we were extracting, resume directly to EXTRACTING
            # Otherwise, use PENDING (which defaults to STRUCTURING in Orchestrator)
            should_resume_extracting = False
            if task.progress:
                try:
                    prog = json.loads(task.progress)
                    if prog.get("phase") == "EXTRACTING":
                        should_resume_extracting = True
                except: pass
            
            if should_resume_extracting:
                task.status = "EXTRACTING"
                print(f"Resuming task {task.id} directly to EXTRACTING phase.")
            else:
                task.status = "PENDING"
                
            task.is_paused = False
            db.commit()
            
            # 4. Re-read content
            # Handle both old format (list of strings) and new format (list of dicts)
            target_files = json.loads(task.target_files) if task.target_files else []
            full_content = []
            
            if target_files and isinstance(target_files[0], dict):
                # New format: [{"original": "a.txt", "path": "uploads/..."}]
                for file_info in target_files:
                    try:
                        with open(file_info["path"], "r", encoding="utf-8") as f:
                            c = f.read()
                            full_content.append(f"--- File: {file_info['original']} ---\n{c}\n")
                    except Exception as e:
                        print(f"Error reading file {file_info}: {e}")
            else:
                # Old format: ["a.txt", "b.txt"] or empty
                # Fallback to task.file_path (only first file available)
                print(f"Warning: Task {task_id} has old target_files format. Only main file will be processed.")
                with open(task.file_path, "r", encoding="utf-8") as f:
                    c = f.read()
                    full_content.append(f"--- File: Main ---\n{c}\n")
            
            combined_text = "\n".join(full_content)
            
            # Use combined_text instead of single file content
            background_tasks.add_task(
                run_orchestrator_task, 
                str(task.id), 
                combined_text, 
                str(task.bot_structure_id), 
                str(task.bot_extraction_id)
            )
            return {"status": "resumed", "message": "Task relaunched from suspension."}
            
        except ValueError as e:
             # If allocation fails, queue the task instead of failing
             print(f"Resume Task {task_id} Resource Exhaustion: {e}. Queuing task.")
             task.status = "QUEUED"
             db.commit()
             return {"status": "queued", "message": "Resources busy. Task queued for execution."}
        except Exception as e:
             # If anything else fails (file read, background task), we MUST release the bots
             # because allocate_bot_pair succeeded above
             print(f"Resume Task {task_id} Exception: {e}")
             if 'agent_manager' in locals() and 'task' in locals():
                 try:
                     agent_manager.release_bot_pair(str(task.id))
                 except: pass
             raise HTTPException(status_code=500, detail=f"Resume failed: {e}")

    # Standard Resume (Unpause)
    task.is_paused = False
    db.commit()
    return {"status": "resumed"}

@router.post("/{task_id}/stop")
def stop_task(task_id: str, db: Session = Depends(get_db)):
    """Manual stop (Sets status to STOPPED)."""
    task = db.query(SysTask).filter(SysTask.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Mark as STOPPED (Partial Success) so orchestrator stops loops
    # Orchestrator handles the rest (release bots, etc.)
    # We set status to CANCELLED first to break the loop, but we want final state STOPPED.
    # The orchestrator checks for CANCELLED.
    # Let's use STOPPED as the signal to break loops too.
    task.status = "STOPPED"
    task.is_paused = False # Resume if paused so it can exit
    
    # Release bots immediately in case orchestrator is stuck
    agent_manager = AgentManager(db)
    agent_manager.release_bot_pair(task_id)
    
    db.commit()
    return {"status": "stopped", "message": "Task marked as stopped. Partial results saved."}

@router.post("/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    """Alias for stop."""
    return stop_task(task_id, db)

@router.delete("/{task_id}")
def delete_task(task_id: str, db: Session = Depends(get_db)):
    """Delete a task and all its associated data."""
    try:
        task = db.query(SysTask).filter(SysTask.id == task_id).first()
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
            
        # 1. Release Resources if held
        agent_manager = AgentManager(db)
        agent_manager.release_bot_pair(task_id)
        
        # 2. Delete Associated Data
        # Find all entities for this task
        # We use subqueries to delete related records
        
        # Delete Attributes
        db.query(EntityAttribute).filter(
            EntityAttribute.entity_id.in_(
                db.query(Entity.id).filter(Entity.task_id == task_id)
            )
        ).delete(synchronize_session=False)
        
        # Delete TextSegments
        db.query(TextSegment).filter(
            TextSegment.entity_id.in_(
                db.query(Entity.id).filter(Entity.task_id == task_id)
            )
        ).delete(synchronize_session=False)
        
        # Delete Entities
        # Note: Self-referential FK might cause issues if not handled. 
        # SQLite usually allows deleting parent and child in same statement if cascade is on, 
        # but here we don't have cascade.
        # We might need to break links first? 
        # Let's try deleting. If it fails, we set parent_id=None first.
        try:
            db.query(Entity).filter(Entity.task_id == task_id).delete(synchronize_session=False)
        except Exception:
            # Fallback: Break parent links then delete
            db.rollback() # Rollback the failed delete
            db.query(Entity).filter(Entity.task_id == task_id).update({"parent_id": None}, synchronize_session=False)
            db.commit() # Commit the break
            db.query(Entity).filter(Entity.task_id == task_id).delete(synchronize_session=False)

        # 3. Delete Task
        db.delete(task)
        db.commit()
        
        return {"status": "deleted", "message": f"Task {task_id} deleted successfully."}
    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Delete failed: {str(e)}")
