from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    telegram_id: int
    username: Optional[str] = None

class UserCreate(UserBase):
    referrer_code: Optional[str] = None

class UserResponse(UserBase):
    ton_balance: float
    stars_balance: int
    referral_code: str
    earned_from_refs: float
    created_at: datetime

class TransactionBase(BaseModel):
    amount: float
    currency: str
    tx_type: str  # deposit/withdraw/ref_bonus

class TransactionCreate(TransactionBase):
    tx_hash: Optional[str] = None

class TransactionResponse(TransactionBase):
    id: int
    status: str
    timestamp: datetime

class YooMoneyWebhook(BaseModel):
    event: str
    object: dict