"""API configuration using Pydantic Settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """API configuration loaded from environment."""

    PROJECT_NAME: str = "CM Agents API"
    VERSION: str = "0.1.0"
    ENVIRONMENT: str = "development"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # Security
    API_KEY: str = ""  # If set, requires X-API-Key header
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:3001",  # Docker frontend (puerto 3001)
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # Paths
    BRANDS_DIR: str = "brands"
    OUTPUTS_DIR: str = "outputs"
    KNOWLEDGE_DIR: str = "knowledge"

    # AI API Keys (loaded from .env)
    OPENAI_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    @property
    def is_production(self) -> bool:
        """Check if running in production."""
        return self.ENVIRONMENT == "production"

    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins, stricter in production."""
        if self.is_production and not self.CORS_ORIGINS:
            # In production with no explicit origins, deny all
            return []
        return self.CORS_ORIGINS

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
