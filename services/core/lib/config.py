"""Configuration management using Pydantic Settings."""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Ollama
    ollama_api_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:3b-instruct"

    # Hotel DB
    db_hotel_host: str = "db_hotel"
    db_hotel_port: int = 5432
    db_hotel_name: str = "hotel_db"
    db_hotel_user: str = "hotel_user"
    db_hotel_password: str = "hotel_password"

    # Payments DB
    db_payments_host: str = "db_payments"
    db_payments_port: int = 5433
    db_payments_name: str = "payments_db"
    db_payments_user: str = "payments_user"
    db_payments_password: str = "payments_password"

    # RAG DB
    db_rag_host: str = "db_rag"
    db_rag_port: int = 5434
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

    # External URLs
    system_whatsapp_sender_url: str = "http://whatsapp-sender:8001"
    system_payment_url: str = "http://payment-system:8003"

    # Mercado Pago
    mp_access_token: str | None = None
    mp_api_url: str = "https://api.mercadopago.com"
    mp_sandbox: bool = True

    # Admin
    admin_phones: str = ""

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
        raw = os.getenv("ADMIN_PHONES", self.admin_phones)
        return [p.strip() for p in raw.split(",") if p.strip()]


settings = Settings()