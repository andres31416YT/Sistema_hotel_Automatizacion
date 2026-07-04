"""Configuration management using Pydantic Settings."""
import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

_env_path = str(Path(__file__).resolve().parent.parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=_env_path, extra="ignore")

    # Ollama
    ollama_api_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:3b-instruct"

    # LangSmith
    langsmith_api_key: str | None = None
    langsmith_tracing: bool = False
    langsmith_endpoint: str = "https://api.smith.langchain.com"
    langsmith_project: str | None = None

    # Hotel DB
    db_hotel_host: str = "db_hotel"
    db_hotel_port: int = 5432
    db_hotel_name: str = "hotel_db"
    db_hotel_user: str = "hotel_user"
    db_hotel_password: str = "hotel_password"

    # Payments DB
    db_payments_host: str = "db_payments"
    db_payments_port: int = 5432
    db_payments_name: str = "payments_db"
    db_payments_user: str = "payments_user"
    db_payments_password: str = "payments_password"

    # RAG DB
    db_rag_host: str = "db_rag"
    db_rag_port: int = 5432
    db_rag_name: str = "rag_db"
    db_rag_user: str = "rag_user"
    db_rag_password: str = "rag_password"

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379
    redis_password: str | None = "redispassword"
    redis_ttl_chat: int = 1800
    redis_ttl_session: int = 3600
    redis_ttl_profile: int = 86400
    redis_ttl_payment: int = 900
    redis_ttl_security: int = 3600
    redis_ttl_contact: int = 86400  # JID cache for LID resolution

    # External URLs
    system_payment_url: str = "http://payment-system:8003"

    # Mercado Pago
    mp_access_token: str | None = None
    mp_api_url: str = "https://api.mercadopago.com"
    mp_sandbox: bool = True

    # OpenWA
    openwa_api_url: str = "http://whatsapp:2785"
    openwa_api_key: str | None = None
    openwa_session_id: str = "hotel"
    openwa_session_uuid: str | None = None
    openwa_webhook_secret: str | None = None

    # Admin
    admin_phones: str = ""

    # RAG
    rag_provider: str = "pgvector"
    rag_turbovec_path: str = "data/turbovec_index.tq"
    rag_turbovec_bit_width: int = 4

    # App
    core_port: int = 8080

    @property
    def hotel_dsn(self) -> str:
        return (
            f"postgresql://{self.db_hotel_user}:{self.db_hotel_password}"
            f"@{self.db_hotel_host}:{self.db_hotel_port}/{self.db_hotel_name}"
        )

    @property
    def payments_dsn(self) -> str:
        return (
            f"postgresql://{self.db_payments_user}:{self.db_payments_password}"
            f"@{self.db_payments_host}:{self.db_payments_port}/{self.db_payments_name}"
        )

    @property
    def rag_dsn(self) -> str:
        return (
            f"postgresql://{self.db_rag_user}:{self.db_rag_password}"
            f"@{self.db_rag_host}:{self.db_rag_port}/{self.db_rag_name}"
        )

    @property
    def admin_phones_list(self) -> list[str]:
        raw = os.getenv("ADMIN_PHONES") or self.admin_phones or ""
        return [p.strip() for p in raw.split(",") if p.strip()]


settings = Settings()