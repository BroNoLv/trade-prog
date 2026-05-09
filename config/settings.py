import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram Bot
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7485766211:AAFrPklOiiQYObWmUQs0JQHpOjY5OD1qH2o")
    
    # Database
    # Support for DATABASE_URL (Neon) or individual parameters
    DATABASE_URL = os.getenv("DATABASE_URL", None)
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_NAME = os.getenv("DB_NAME", "bot_db")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "138616era")
    DB_PORT = os.getenv("DB_PORT", "5432")
    
    # USDT
    OWNER_WALLET_ADDRESS = os.getenv("OWNER_WALLET_ADDRESS", "TXYZ1234567890abcdefghijklmnopqrstuvw")
    EXCHANGE_RATE_API = os.getenv("EXCHANGE_RATE_API", "https://rapira.net/exchange/USDT_RUB")
    
    # Proxy settings (optional)
    PROXY_URL = os.getenv("PROXY_URL", None)
    
    # Bot settings
    PAYMENT_TIMEOUT = 30 * 60  # 30 minutes in seconds
    REQUIRED_INSURANCE_DEPOSIT = 1000  # USDT
    
    # User roles
    ROLE_OWNER = "owner"
    ROLE_TRADER = "trader"
    ROLE_OPERATOR = "operator"
    
    @property
    def database_url(self):
        """Возвращает DATABASE_URL если задан, иначе формирует из параметров"""
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

config = Config()