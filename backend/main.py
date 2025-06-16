import os
from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from datetime import datetime
from pytonconnect import TonConnect
import sqlite3
import hashlib
import hmac
import json
import requests
from typing import Optional

app = FastAPI()
security = HTTPBearer()

# Конфигурация
TON_WALLET = os.getenv('TON_WALLET', 'EQCbaFt3eQy4r7e3Qq1XOyW2N9l5nQvJ2Aiy8G4VZpQkL1bh')
BOT_TOKEN = os.getenv('BOT_TOKEN', 'YOUR_BOT_TOKEN')
YOOKASSA_SHOP_ID = os.getenv('YOOKASSA_SHOP_ID')
YOOKASSA_SECRET_KEY = os.getenv('YOOKASSA_SECRET_KEY')
YOOKASSA_URL = "https://api.yookassa.ru/v3"
REFERRAL_BONUS = 0.5  # 50% от суммы депозита


# Модели данных
class UserCreate(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    referrer_code: Optional[str] = None


class PaymentRequest(BaseModel):
    amount: float
    currency: str
    tx_hash: Optional[str] = None


class YooMoneyPayment(BaseModel):
    payment_id: str
    status: str
    amount: float
    currency: str


# Инициализация БД
def get_db():
    conn = sqlite3.connect('walletstars.db')
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS users
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       telegram_id
                       INTEGER
                       UNIQUE,
                       username
                       TEXT,
                       ton_balance
                       REAL
                       DEFAULT
                       0,
                       stars_balance
                       INTEGER
                       DEFAULT
                       0,
                       rub_balance
                       REAL
                       DEFAULT
                       0,
                       referrer_id
                       INTEGER,
                       referral_code
                       TEXT
                       UNIQUE,
                       earned_from_refs
                       REAL
                       DEFAULT
                       0,
                       referrals_count
                       INTEGER
                       DEFAULT
                       0,
                       created_at
                       DATETIME
                       DEFAULT
                       CURRENT_TIMESTAMP
                   )
                   ''')

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS transactions
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       user_id
                       INTEGER,
                       amount
                       REAL,
                       currency
                       TEXT,
                       tx_type
                       TEXT,
                       #
                       'deposit',
                       'buy_stars',
                       'ref_bonus'
                       tx_hash
                       TEXT
                       UNIQUE,
                       status
                       TEXT
                       DEFAULT
                       'pending',
                       timestamp
                       DATETIME
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       FOREIGN
                       KEY
                   (
                       user_id
                   ) REFERENCES users
                   (
                       id
                   )
                       )
                   ''')

    cursor.execute('''
                   CREATE TABLE IF NOT EXISTS referral_payments
                   (
                       id
                       INTEGER
                       PRIMARY
                       KEY
                       AUTOINCREMENT,
                       referrer_id
                       INTEGER,
                       referral_id
                       INTEGER,
                       amount
                       REAL,
                       currency
                       TEXT,
                       timestamp
                       DATETIME
                       DEFAULT
                       CURRENT_TIMESTAMP,
                       FOREIGN
                       KEY
                   (
                       referrer_id
                   ) REFERENCES users
                   (
                       id
                   ),
                       FOREIGN KEY
                   (
                       referral_id
                   ) REFERENCES users
                   (
                       id
                   )
                       )
                   ''')

    conn.commit()
    conn.close()


init_db()


# Валидация Telegram WebApp
async def verify_telegram_data(telegram_data: str = Header(None)):
    if not telegram_data:
        raise HTTPException(status_code=401, detail="Telegram data required")

    try:
        data = dict(pair.split('=') for pair in telegram_data.split('&'))
        hash_str = data.pop('hash')

        secret_key = hashlib.sha256(BOT_TOKEN.encode()).digest()
        data_check_string = '\n'.join(f"{k}={v}" for k, v in sorted(data.items()))

        computed_hash = hmac.new(secret_key,
                                 msg=data_check_string.encode(),
                                 digestmod=hashlib.sha256).hexdigest()

        if computed_hash != hash_str:
            raise HTTPException(status_code=403, detail="Invalid Telegram hash")

        return json.loads(data['user'])
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid data: {str(e)}")


# Регистрация пользователя
@app.post("/register")
async def register_user(user: UserCreate, user_data: dict = Depends(verify_telegram_data)):
    conn = get_db()
    try:
        # Генерация реферального кода
        referral_code = hashlib.sha256(f"{user.telegram_id}{datetime.now()}".encode()).hexdigest()[:8]

        # Поиск реферера
        referrer_id = None
        if user.referrer_code:
            cur = conn.execute("SELECT id FROM users WHERE referral_code = ?", (user.referrer_code,))
            referrer = cur.fetchone()
            if referrer:
                referrer_id = referrer['id']

        conn.execute(
            """
            INSERT INTO users
                (telegram_id, username, referral_code, referrer_id)
            VALUES (?, ?, ?, ?)
            """,
            (user.telegram_id, user.username, referral_code, referrer_id)
        )

        # Начисление бонуса рефереру
        if referrer_id:
            conn.execute(
                """
                UPDATE users
                SET referrals_count = referrals_count + 1
                WHERE id = ?
                """,
                (referrer_id,)
            )

        conn.commit()
        return {"status": "success", "referral_code": referral_code}
    except sqlite3.IntegrityError:
        raise HTTPException(400, "User already exists")
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


# Обработка TON платежа
@app.post("/process_ton")
async def process_ton_payment(
        tx_hash: str,
        amount: float,
        user_data: dict = Depends(verify_telegram_data)
):
    conn = get_db()
    try:
        # Проверка дубликата транзакции
        cur = conn.execute("SELECT id FROM transactions WHERE tx_hash = ?", (tx_hash,))
        if cur.fetchone():
            raise HTTPException(400, "Transaction already processed")

        # Получение данных пользователя
        cur = conn.execute(
            "SELECT id, referrer_id FROM users WHERE telegram_id = ?",
            (user_data['id'],)
        )
        user = cur.fetchone()
        if not user:
            raise HTTPException(404, "User not found")

        user_id, referrer_id = user['id'], user['referrer_id']

        # Начисление бонуса рефереру
        if referrer_id:
            bonus = amount * REFERRAL_BONUS
            conn.execute(
                """
                UPDATE users
                SET ton_balance      = ton_balance + ?,
                    earned_from_refs = earned_from_refs + ?
                WHERE id = ?
                """,
                (bonus, bonus, referrer_id)
            )

            # Запись реферальной транзакции
            conn.execute(
                """
                INSERT INTO referral_payments
                    (referrer_id, referral_id, amount, currency)
                VALUES (?, ?, ?, 'TON')
                """,
                (referrer_id, user_id, bonus)
            )

        # Конвертация в звёзды
        stars = int(amount / 0.1)  # 1 звезда = 0.1 TON

        # Обновление баланса
        conn.execute(
            """
            UPDATE users
            SET ton_balance   = ton_balance + ?,
                stars_balance = stars_balance + ?
            WHERE id = ?
            """,
            (amount, stars, user_id)
        )

        # Запись транзакции
        conn.execute(
            """
            INSERT INTO transactions
                (user_id, amount, currency, tx_type, tx_hash, status)
            VALUES (?, ?, 'TON', 'deposit', ?, 'completed')
            """,
            (user_id, amount, tx_hash)
        )

        conn.commit()
        return {"status": "success", "stars_added": stars}
    except Exception as e:
        conn.rollback()
        raise HTTPException(500, str(e))
    finally:
        conn.close()


# Получение реферальной статистики
@app.get("/ref_stats")
async def get_ref_stats(user_data: dict = Depends(verify_telegram_data)):
    conn = get_db()
    try:
        cur = conn.execute(
            """
            SELECT u.referral_code,
                   COUNT(rp.id)                as referrals_count,
                   COALESCE(SUM(rp.amount), 0) as earned_total
            FROM users u
                     LEFT JOIN referral_payments rp ON u.id = rp.referrer_id
            WHERE u.telegram_id = ?
            GROUP BY u.referral_code
            """,
            (user_data['id'],)
        )
        stats = cur.fetchone()

        if not stats:
            raise HTTPException(404, "Stats not found")

        return {
            "referral_code": stats['referral_code'],
            "referrals_count": stats['referrals_count'] or 0,
            "earned_total": float(stats['earned_total'] or 0)
        }
    except Exception as e:
        raise HTTPException(500, str(e))
    finally:
        conn.close()


# ЮMoney платежи
@app.post("/create_yoomoney_payment")
async def create_yoomoney_payment(
        amount: float,
        user_data: dict = Depends(verify_telegram_data)
):
    try:
        payment_data = {
            "amount": {"value": amount, "currency": "RUB"},
            "payment_method_data": {"type": "bank_card"},
            "confirmation": {
                "type": "redirect",
                "return_url": f"https://t.me/{BOT_TOKEN}"
            },
            "description": "Покупка звезд",
            "metadata": {"user_id": user_data['id']}
        }

        response = requests.post(
            f"{YOOKASSA_URL}/payments",
            json=payment_data,
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY)

        if response.status_code != 200:
            raise HTTPException(400, "Payment creation failed")

        return response.json()
    except Exception as e:
        raise HTTPException(500, str(e))


# Вебхук для ЮMoney
@app.post("/yookassa_webhook")
async def yookassa_webhook(notification: dict, request: Request):
    try:
        # Валидация подписи
        body = await request.body()
        expected_sign = hmac.new(
            YOOKASSA_SECRET_KEY.encode(),
            body,
            hashlib.sha256
        ).hexdigest()

        if request.headers.get('Content-SHA256') != expected_sign:
            raise HTTPException(403, "Invalid signature")

        # Обработка платежа
        if notification['event'] == 'payment.succeeded':
            payment = notification['object']
            user_id = payment['metadata']['user_id']
            amount = float(payment['amount']['value'])

            # Конвертация в звёзды (1 звезда = 10 RUB)
            stars = int(amount / 10)

            conn = get_db()
            conn.execute(
                """
                UPDATE users
                SET rub_balance   = rub_balance + ?,
                    stars_balance = stars_balance + ?
                WHERE telegram_id = ?
                """,
                (amount, stars, user_id)
            )
            conn.commit()

        return {"status": "processed"}
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)