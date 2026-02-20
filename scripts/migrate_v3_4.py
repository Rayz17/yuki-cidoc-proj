import sys
import os
from sqlalchemy import create_engine, text

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config import settings

def migrate():
    print("Starting migration to V3.4...")
    
    engine = create_engine(settings.DATABASE_URL)
    
    with engine.connect() as conn:
        # Create system_settings table
        print("Creating system_settings table...")
        try:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS system_settings (
                    id CHAR(36) PRIMARY KEY,
                    key VARCHAR(100) NOT NULL UNIQUE,
                    value TEXT,
                    description TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
            print("- Created system_settings table")
        except Exception as e:
            print(f"- Error creating table: {e}")
            
        conn.commit()
    
    print("Migration V3.4 complete.")

if __name__ == "__main__":
    migrate()
