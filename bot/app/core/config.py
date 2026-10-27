from functools import lru_cache
import re
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    environment: Literal["development", "test", "staging", "production"] = "development"
    bot_token: SecretStr
    telegram_webhook_secret: SecretStr
    public_base_url: str
    postgres_dsn: SecretStr
    redis_url: SecretStr
    super_admin_ids: str = ""
    app_secret: SecretStr
    pii_encryption_key: SecretStr
    phone_hash_key: SecretStr
    default_language: Literal["uz", "ru"] = "uz"
    timezone: str = "Asia/Tashkent"
    hold_minutes: int = Field(default=15, ge=1, le=60)
    booking_horizon_days: int = Field(default=30, ge=1, le=365)
    booking_cutoff_minutes: int = Field(default=60, ge=0, le=1440)
    max_active_holds: int = Field(default=3, ge=1, le=10)
    support_contact: str = "@support"
    manual_payment_enabled: bool = True
    payme_enabled: bool = False
    click_enabled: bool = False
    sentry_dsn: str | None = None
    log_level: str = "INFO"

    @field_validator("public_base_url")
    @classmethod
    def validate_public_url(cls, value: str) -> str:
        value = value.rstrip("/")
        if not value.startswith("https://"):
            raise ValueError("PUBLIC_BASE_URL HTTPS bo‘lishi kerak")
        return value

    @field_validator("telegram_webhook_secret")
    @classmethod
    def validate_webhook_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()
        if len(secret) < 16 or re.fullmatch(r"[A-Za-z0-9_-]+", secret) is None:
            raise ValueError("TELEGRAM_WEBHOOK_SECRET kamida 16 ta URL-safe belgidan iborat bo‘lsin")
        return value

    @field_validator("app_secret")
    @classmethod
    def validate_app_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("APP_SECRET kamida 32 belgidan iborat bo‘lsin")
        return value

    @field_validator("phone_hash_key")
    @classmethod
    def validate_phone_hash_key(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 16:
            raise ValueError("PHONE_HASH_KEY kamida 16 belgidan iborat bo‘lsin")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        ZoneInfo(value)
        return value

    @property
    def admin_ids(self) -> frozenset[int]:
        return frozenset(int(item.strip()) for item in self.super_admin_ids.split(",") if item.strip())

    @property
    def webhook_url(self) -> str:
        return f"{self.public_base_url}/webhooks/telegram"

    @property
    def tzinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
