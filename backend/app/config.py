import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = Field(default="sqlite+aiosqlite:///./app.db")

    # Redis
    REDIS_URL: str = Field(default="redis://redis:6379")

    # JWT
    SECRET_KEY: str = Field(default="change-me-in-production-super-secret-key-12345678")
    ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=1440)  # 24 hours

    # File storage
    UPLOAD_DIR: str = Field(default="./uploads")
    TEMPLATE_DIR: str = Field(default="./templates")
    SANDBOX_WORKSPACE: str = Field(default="./sandbox_workspace")

    # LLM defaults
    DEFAULT_LLM_BASE_URL: str = Field(default="https://api.openai.com/v1")
    DEFAULT_LLM_MODEL: str = Field(default="gpt-4o")
    DEFAULT_LLM_API_KEY: str = Field(default="")

    # Feature flags
    ENABLE_EXTERNAL_SEARCH: bool = Field(default=False)
    ENABLE_BROWSER: bool = Field(default=True)
    SANDBOX_TIMEOUT: int = Field(default=30)
    MAX_WORKERS: int = Field(default=10)

    # App settings
    APP_NAME: str = Field(default="Multi-Agent AI Platform")
    DEBUG: bool = Field(default=False)
    CORS_ORIGINS: list = Field(default=["*"])

    # Default admin
    DEFAULT_ADMIN_USERNAME: str = Field(default="admin")
    DEFAULT_ADMIN_PASSWORD: str = Field(default="990115")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
