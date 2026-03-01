from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from src.db.database import get_db
from src.db.models import MasterEntity, MasterAttribute
import csv
import io

router = APIRouter()

def generate_master_csv_stream(query, db: Session):
    """Generator for streaming master data CSV export."""
    output = io.StringIO()
    # Define columns
    fieldnames = ["Entity ID", "Site Name", "Name", "Type", "Updated At", "Attribute Code", "Attribute Value", "Quote"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    # Yield header
    yield output.getvalue()
    output.seek(0)
    output.truncate(0)
    
    batch_size = 1000
    offset = 0
    
    while True:
        # Fetch batch with attributes eager loaded
        entities = query.options(joinedload(MasterEntity.attributes))\
            .order_by(MasterEntity.updated_at.desc())\
            .offset(offset).limit(batch_size).all()
            
        if not entities:
            break
            
        for entity in entities:
            base_row = {
                "Entity ID": str(entity.id),
                "Site Name": entity.site_name,
                "Name": entity.name,
                "Type": entity.entity_type,
                "Updated At": entity.updated_at.isoformat() if entity.updated_at else ""
            }
            
            attributes = entity.attributes
            
            if not attributes:
                row = base_row.copy()
                row["Attribute Code"] = ""
                row["Attribute Value"] = ""
                row["Quote"] = ""
                writer.writerow(row)
            else:
                for attr in attributes:
                    row = base_row.copy()
                    row["Attribute Code"] = attr.attribute_code
                    row["Attribute Value"] = attr.attribute_value
                    row["Quote"] = attr.quote
                    writer.writerow(row)
        
        # Yield batch
        yield output.getvalue()
        output.seek(0)
        output.truncate(0)
        
        offset += batch_size

@router.get("/export")
def export_master_entities(
    site_name: str = None, 
    entity_type: str = None,
    db: Session = Depends(get_db)
):
    """
    Export all matching master entities to CSV via Stream.
    """
    query = db.query(MasterEntity)
    
    if site_name:
        query = query.filter(MasterEntity.site_name.contains(site_name))
    if entity_type:
        query = query.filter(MasterEntity.entity_type == entity_type)
        
    return StreamingResponse(
        generate_master_csv_stream(query, db),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=master_data_export.csv"}
    )

@router.get("/entities", response_model=dict)
def list_master_entities(
    site_name: str = None, 
    entity_type: str = None,
    page: int = 1, 
    size: int = 50, 
    db: Session = Depends(get_db)
):
    """
    List consolidated master entities with pagination.
    """
    query = db.query(MasterEntity)
    
    if site_name:
        # Use ILIKE for case-insensitive search if supported, or just simple match
        query = query.filter(MasterEntity.site_name.contains(site_name))
    if entity_type:
        query = query.filter(MasterEntity.entity_type == entity_type)
        
    total = query.count()
    
    skip = (page - 1) * size
    entities = query.order_by(MasterEntity.updated_at.desc()).offset(skip).limit(size).all()
    
    results = []
    for entity in entities:
        # Fetch attributes (rich view)
        attributes = entity.attributes # Use relationship
        attr_dict = {attr.attribute_code: {"value": attr.attribute_value, "quote": attr.quote} for attr in attributes}
        
        results.append({
            "id": str(entity.id),
            "site_name": entity.site_name,
            "type": entity.entity_type,
            "name": entity.name,
            "attributes": attr_dict,
            "updated_at": entity.updated_at
        })
        
    return {
        "total": total,
        "page": page,
        "size": size,
        "items": results
    }
