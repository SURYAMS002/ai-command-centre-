import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    APP_NAME: str = "AI Farm Operations Command Center (AFOCC)"
    VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database
    DATABASE_PATH: Path = BASE_DIR / "data" / "afocc.db"
    SEED_DATA_PATH: Path = BASE_DIR / "data" / "farm_data.json"
    
    # OpenAI (For Phase 3 onwards)
    OPENAI_API_KEY: str = ""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
