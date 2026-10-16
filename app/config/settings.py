import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent.parent

class Settings:
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # Telegram Channel (public ExchangeWatch alert feed)
    TELEGRAM_CHANNEL_ENABLED: bool = os.getenv("TELEGRAM_CHANNEL_ENABLED", "false").lower() == "true"
    TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")

    POLL_INTERVAL_SECONDS: int = int(os.getenv("POLL_INTERVAL_SECONDS", "15"))

    LOCAL_AI_ENABLED: bool = os.getenv("LOCAL_AI_ENABLED", "true").lower() == "true"
    LOCAL_AI_URL: str = os.getenv("LOCAL_AI_URL", "http://localhost:11434/api/generate")
    LOCAL_AI_MODEL: str = os.getenv("LOCAL_AI_MODEL", "llama3.2:1b")
    LOCAL_AI_TIMEOUT_SECONDS: int = int(os.getenv("LOCAL_AI_TIMEOUT_SECONDS", "10"))
    LOCAL_AI_SELECTIVE: bool = os.getenv("LOCAL_AI_SELECTIVE", "true").lower() == "true"
    AI_PROCESSING_MODE: str = os.getenv("AI_PROCESSING_MODE", "FAST_NLP_FIRST")

    DATABASE_PATH: Path = BASE_DIR / os.getenv("DATABASE_PATH", "data/exchangewatch.db")
    EXCEL_OUTPUT_PATH: Path = BASE_DIR / os.getenv("EXCEL_OUTPUT_PATH", "output/ExchangeWatch_AI_Alerts.xlsx")
    CSV_OUTPUT_PATH: Path = BASE_DIR / os.getenv("CSV_OUTPUT_PATH", "output/ExchangeWatch_AI_Alerts.csv")

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

settings = Settings()

# Ensure directories exist
settings.DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
settings.EXCEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
