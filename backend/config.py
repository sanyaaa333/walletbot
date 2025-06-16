import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # TON
    TON_WALLET: str = os.getenv("TON_WALLET")
    STAR_PRICE_TON: float = 0.1

    # ЮMoney
    YOOKASSA_SHOP_ID: str = os.getenv("YOOKASSA_SHOP_ID")
    YOOKASSA_SECRET_KEY: str = os.getenv("YOOKASSA_SECRET_KEY")
    STAR_PRICE_RUB: int = 10

    # Реферальная система
    REFERRAL_BONUS: float = 0.5  # 50%

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN")

    # БД
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./walletstars.db")


settings = Settings()