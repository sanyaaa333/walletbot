from fastapi import APIRouter, Request, HTTPException
import hmac
import hashlib
from config import settings
from models import YooMoneyWebhook
import database

router = APIRouter(prefix="/yookassa")


@router.post("/webhook")
async def handle_webhook(
        notification: YooMoneyWebhook,
        request: Request
):
    # Валидация подписи
    body = await request.body()
    sign = hmac.new(
        settings.YOOKASSA_SECRET_KEY.encode(),
        body,
        hashlib.sha256
    ).hexdigest()

    if request.headers.get('Content-SHA256') != sign:
        raise HTTPException(403, "Invalid signature")

    # Обработка успешного платежа
    if notification.event == "payment.succeeded":
        payment = notification.object
        user_id = payment.metadata.get("user_id")
        amount = float(payment.amount.value)

        with database.get_db() as conn:
            # Начисление RUB и звезд
            stars = int(amount / settings.STAR_PRICE_RUB)
            conn.execute(
                """
                UPDATE users
                SET rub_balance   = rub_balance + ?,
                    stars_balance = stars_balance + ?
                WHERE telegram_id = ?
                """,
                (amount, stars, user_id)
            )

            # Реферальный бонус (если есть реферер)
            conn.execute(
                """
                UPDATE users u
                SET earned_from_refs = earned_from_refs + ? FROM (
                    SELECT referrer_id 
                    FROM users 
                    WHERE telegram_id = ?
                ) AS ref
                WHERE u.id = ref.referrer_id
                """,
                (amount * settings.REFERRAL_BONUS, user_id)
            )

    return {"status": "processed"}