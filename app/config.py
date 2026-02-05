import logging
import uuid

from pydantic_settings import BaseSettings

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    # Twilio
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    user_phone: str = ""

    # Anthropic
    anthropic_api_key: str = ""
    ai_model: str = "claude-haiku-4-5-20251001"

    # Admin auth — no default; generated at startup if missing
    admin_api_key: str = ""

    # Scheduling
    timezone: str = "America/Los_Angeles"
    daily_send_hour: int = 8
    daily_send_minute: int = 0
    weekly_review_day: str = "sun"  # mon, tue, wed, thu, fri, sat, sun
    weekly_review_hour: int = 18

    # SMS
    sms_char_limit: int = 1500

    # Plan
    default_plan_id: int = 1

    # Database
    database_url: str = "gtm_bot.db"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()

# Generate a random admin key if none was provided
if not settings.admin_api_key:
    generated = uuid.uuid4().hex
    settings.admin_api_key = generated
    logger.warning("ADMIN_API_KEY not set — generated ephemeral key: %s", generated)


def validate_settings() -> None:
    """Fail fast on startup if critical config is missing."""
    missing = []
    if not settings.twilio_account_sid:
        logger.warning("TWILIO_ACCOUNT_SID not set — SMS sending disabled (dev mode)")
    if not settings.anthropic_api_key:
        missing.append("ANTHROPIC_API_KEY")
    if missing:
        raise RuntimeError(f"Missing required settings: {', '.join(missing)}")
