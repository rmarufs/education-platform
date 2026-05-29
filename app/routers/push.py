from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.database import get_db
from app.models.user import PushSubscription
from app.dependencies import get_user
from app.config import VAPID_PUBLIC_KEY

router = APIRouter(prefix="/api/push", tags=["Push Notifications"])


class PushKeys(BaseModel):
    p256dh: str
    auth: str


class PushSubscriptionCreate(BaseModel):
    endpoint: str
    keys: PushKeys


class PushUnsubscribe(BaseModel):
    endpoint: str


@router.get("/public-key")
def get_public_key():
    if not VAPID_PUBLIC_KEY:
        raise HTTPException(status_code=500, detail="VAPID_PUBLIC_KEY not configured on server")
    return {"public_key": VAPID_PUBLIC_KEY}


@router.post("/subscribe")
def subscribe_push(
    subscription: PushSubscriptionCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    
    existing_sub = db.query(PushSubscription).filter(PushSubscription.endpoint == subscription.endpoint).first()
    user_agent = request.headers.get("user-agent")

    if existing_sub:
        existing_sub.user_id = user.id
        existing_sub.p256dh = subscription.keys.p256dh
        existing_sub.auth = subscription.keys.auth
        existing_sub.user_agent = user_agent
    else:
        new_sub = PushSubscription(
            user_id=user.id,
            endpoint=subscription.endpoint,
            p256dh=subscription.keys.p256dh,
            auth=subscription.keys.auth,
            user_agent=user_agent
        )
        db.add(new_sub)
    
    db.commit()
    return {"status": "success", "message": "Subscription saved"}


@router.post("/unsubscribe")
def unsubscribe_push(
    payload: PushUnsubscribe,
    request: Request,
    db: Session = Depends(get_db)
):
    user = get_user(request, db)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")

    sub = db.query(PushSubscription).filter(
        PushSubscription.endpoint == payload.endpoint,
        PushSubscription.user_id == user.id
    ).first()
    
    if sub:
        db.delete(sub)
        db.commit()
        return {"status": "success", "message": "Subscription removed"}
    
    return {"status": "not_found", "message": "Subscription not found"}
