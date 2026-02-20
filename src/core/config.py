import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Archaeo Extractor V2"
    API_V1_STR: str = "/api/v1"
    
    # Database
    # Default to sqlite for local dev if not provided
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./archaeo_data.db")
    
    # Coze API
    COZE_API_KEY: str = os.getenv("COZE_API_KEY", "")
    COZE_API_BASE: str = os.getenv("COZE_API_BASE", "https://api.coze.com/open_api/v2")
    COZE_BOT_ID_A: str = os.getenv("COZE_BOT_ID_A", "") # StructureBot
    COZE_BOT_ID_B: str = os.getenv("COZE_BOT_ID_B", "") # ExtractionBot
    COZE_BOT_ID_C: str = os.getenv("COZE_BOT_ID_C", "") # DeduplicationBot (Agent C)
    
    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    class Config:
        env_file = ".env"

settings = Settings()
