import json
import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from pywebpush import webpush, WebPushException

from app.models.user import PushSubscription
from app.config import VAPID_PRIVATE_KEY, VAPID_CLAIMS_SUB

logger = logging.getLogger(__name__)


def send_push_to_user(
    db: Session,
    user_id: int,
    title: str,
    body: str,
    target_url: str,
    icon: Optional[str] = "/static/favicon/android-chrome-192x192.png",
    badge: Optional[str] = "/static/favicon/favicon-32x32.png",
    notification_type: Optional[str] = None,
    entity_id: Optional[int] = None
) -> None:
    """
    Отправляет Web Push уведомление конкретному пользователю на все его активные устройства.
    Если VAPID ключи не настроены, просто логирует предупреждение и выходит.
    Невалидные подписки (404, 410) автоматически удаляются из БД.
    Ошибки отправки перехватываются, чтобы не ломать основной бизнес-процесс.
    """
    if not VAPID_PRIVATE_KEY or not VAPID_CLAIMS_SUB:
        logger.warning("VAPID_PRIVATE_KEY or VAPID_CLAIMS_SUB not configured. Push notifications are disabled.")
        return

    subscriptions = db.query(PushSubscription).filter(PushSubscription.user_id == user_id).all()
    if not subscriptions:
        return

    payload = {
        "title": title,
        "body": body,
        "icon": icon,
        "badge": badge,
        "targetUrl": target_url,
        "type": notification_type,
        "entityId": entity_id
    }
    payload_str = json.dumps(payload)

    for sub in subscriptions:
        try:
            subscription_info = {
                "endpoint": sub.endpoint,
                "keys": {
                    "p256dh": sub.p256dh,
                    "auth": sub.auth
                }
            }
            
            webpush(
                subscription_info=subscription_info,
                data=payload_str,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_CLAIMS_SUB}
            )
        except WebPushException as e:
            # 404 (Not Found) or 410 (Gone) indicates the subscription is no longer valid
            if e.response and e.response.status_code in (404, 410):
                logger.info(f"Push subscription for user {user_id} expired or invalid. Removing endpoint: {sub.endpoint}")
                db.delete(sub)
                db.commit()
            else:
                logger.error(f"WebPushException when sending push to user {user_id}: {e}")
        except Exception as e:
            logger.exception(f"Unexpected error when sending push to user {user_id}: {e}")


def send_push_to_users(
    db: Session,
    user_ids: List[int],
    title: str,
    body: str,
    target_url: str,
    icon: Optional[str] = "/static/favicon/android-chrome-192x192.png",
    badge: Optional[str] = "/static/favicon/favicon-32x32.png",
    notification_type: Optional[str] = None,
    entity_id: Optional[int] = None
) -> None:
    """
    Отправляет Web Push уведомление списку пользователей.
    Удаляет дубликаты user_id и вызывает send_push_to_user для каждого.
    """
    unique_user_ids = set(user_ids)
    for uid in unique_user_ids:
        send_push_to_user(
            db=db,
            user_id=uid,
            title=title,
            body=body,
            target_url=target_url,
            icon=icon,
            badge=badge,
            notification_type=notification_type,
            entity_id=entity_id
        )
