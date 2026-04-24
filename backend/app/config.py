from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    gemini_api_key: str
    gemini_model: str = "gemini-1.5-pro"
    tavily_api_key: str

    mongo_uri: str
    mongo_db_name: str = "docanalyzer"

    redis_url: str = "redis://redis:6379"
    redis_ttl_seconds: int = 3600

    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60
    refresh_token_expire_days: int = 7

    max_iterations: int = 10
    confidence_threshold: float = 0.75
    token_budget_per_call: int = 4096
    embedding_dimensions: int = 768
    chunk_size: int = 512
    chunk_overlap: int = 64

    enable_chart_extraction: bool = True
    enable_web_search: bool = True
    enable_audit_log: bool = True
    enable_cost_tracking: bool = True
    enable_metrics_endpoint: bool = True
    enable_streaming: bool = True

    metrics_window_days: int = 1
    metrics_slow_query_ms: int = 3000


    cost_alert_threshold_usd: float = 1.00
    gemini_cost_per_1k_input_tokens: float = 0.00035
    gemini_cost_per_1k_output_tokens: float = 0.00105

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    allowed_origins: str = "http://localhost:3000,http://localhost:5173"

    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"

    @property
    def allowed_origins_list(self) -> list[str]:
        """Retorna ALLOWED_ORIGINS como lista para o CORS do FastAPI."""
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância singleton de Settings (cacheada)."""
    return Settings()


settings = get_settings()
