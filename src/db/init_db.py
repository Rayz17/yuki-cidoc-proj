import logging
from src.db.database import engine, Base
from src.db.models import SysTask, Entity, TextSegment, EntityAttribute

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    logger.info("Creating database tables...")
    try:
        # Create all tables defined in models
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully!")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise e

if __name__ == "__main__":
    print("Initializing Database...")
    init_db()
    print("Done.")
