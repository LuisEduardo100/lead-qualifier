from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env")

    groq_api_key: str = ""
    secret_key: str = "change-this"
    admin_username: str = "admin"
    admin_password: str = "admin123"
    evolution_api_url: str = "http://localhost:8080"
    evolution_api_key: str = "lead-qualifier-key"
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from_name: str = "Consultor Comercial"
    database_url: str = "sqlite+aiosqlite:///./data/leads.db"
    public_url: str = "http://api:8000"
    internal_api_url: str = "http://api:8000"

@lru_cache
def get_settings() -> Settings:
    return Settings()
