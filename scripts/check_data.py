from src.db.database import SessionLocal
from src.db.models import MasterEntity

def check_data():
    db = SessionLocal()
    try:
        count = db.query(MasterEntity).count()
        print(f"Total Master Entities: {count}")
        
        entities = db.query(MasterEntity).limit(5).all()
        for e in entities:
            print(f"- {e.site_name} ({e.entity_type})")
            
    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    check_data()
