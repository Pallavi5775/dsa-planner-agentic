from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.db.session import get_db
from backend.db.models import User, Notification
from backend.core.security import get_current_user_id

router = APIRouter()


@router.get("/me/notifications")
async def get_notifications(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Return the 30 most recent in-app notifications for the current user."""
    rows = (await db.execute(
        select(Notification)
        .where(Notification.user_id == user_id)
        .order_by(Notification.id.desc())
        .limit(30)
    )).scalars().all()
    return [
        {
            "id": n.id,
            "message": n.message,
            "type": n.notif_type,
            "is_read": n.is_read,
            "created_at": n.created_at,
        }
        for n in rows
    ]


@router.patch("/me/notifications/{notif_id}/read")
async def mark_read(
    notif_id: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    notif = (await db.execute(
        select(Notification).where(
            Notification.id == notif_id,
            Notification.user_id == user_id,
        )
    )).scalar_one_or_none()
    if notif is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    await db.commit()
    return {"ok": True}


@router.patch("/me/notifications/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    rows = (await db.execute(
        select(Notification).where(
            Notification.user_id == user_id,
            Notification.is_read == False,  # noqa: E712
        )
    )).scalars().all()
    for n in rows:
        n.is_read = True
    await db.commit()
    return {"marked": len(rows)}


@router.get("/me/notification-settings")
async def get_settings(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return {
        "email_notif_enabled":    user.email_notif_enabled,
        "telegram_notif_enabled": user.telegram_notif_enabled,
        "telegram_chat_id":       user.telegram_chat_id,
        "notify_hour":            user.notify_hour,
    }


@router.patch("/me/notification-settings")
async def update_settings(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    if "email_notif_enabled" in body:
        user.email_notif_enabled = bool(body["email_notif_enabled"])
    if "telegram_notif_enabled" in body:
        user.telegram_notif_enabled = bool(body["telegram_notif_enabled"])
    if "telegram_chat_id" in body:
        user.telegram_chat_id = body["telegram_chat_id"] or None
    if "notify_hour" in body:
        h = int(body["notify_hour"])
        if not 0 <= h <= 23:
            raise HTTPException(status_code=400, detail="notify_hour must be 0–23")
        user.notify_hour = h

    await db.commit()
    return {"ok": True}
