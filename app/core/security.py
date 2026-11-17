import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SESSION_SECRET = os.getenv("OI_ZEUS_SESSION_SECRET", "")
if len(SESSION_SECRET.encode("utf-8")) < 32:
    raise RuntimeError(
        "Defina OI_ZEUS_SESSION_SECRET com pelo menos 32 bytes no ambiente ou no .env."
    )

SESSION_MAX_AGE_SECONDS = 12 * 60 * 60
APP_ENV = os.getenv("APP_ENV", "development").casefold()
SESSION_COOKIE_SECURE = APP_ENV == "production" or os.getenv(
    "OI_ZEUS_COOKIE_SECURE", "false"
).casefold() in {"1", "true", "yes", "on"}