import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "Delivery Infrastructure Platform API"
    API_V1_STR: str = "/api/v1"
    
    # Database Settings
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", 
        "postgresql+asyncpg://postgres:yourpassword@localhost:5432/delivery_platform"
    )
    
    # Redis Settings
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    
    # Security
    API_KEY_HEADER_NAME: str = "X-API-Key"

    class Config:
        case_sensitive = True

settings = Settings()
