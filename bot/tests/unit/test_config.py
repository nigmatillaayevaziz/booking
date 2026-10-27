from cryptography.fernet import Fernet

from app.core.config import Settings


def test_settings_accept_valid_secret_values() -> None:
    settings = Settings(
        bot_token="123456789:abcdefghijklmnopqrstuvwxyzABCDE",
        telegram_webhook_secret="a_secure_webhook_secret_123",
        public_base_url="https://bot.example.uz/",
        postgres_dsn="postgresql+asyncpg://booking:booking@postgres:5432/booking",
        redis_url="redis://redis:6379/0",
        app_secret="a" * 32,
        pii_encryption_key=Fernet.generate_key().decode(),
        phone_hash_key="b" * 32,
    )

    assert settings.public_base_url == "https://bot.example.uz"
    assert settings.webhook_url.endswith("/webhooks/telegram")
    assert str(settings.tzinfo) == "Asia/Tashkent"
