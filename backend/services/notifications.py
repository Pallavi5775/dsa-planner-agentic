import logging
import os
from datetime import datetime, timezone

import httpx

log = logging.getLogger(__name__)

RESEND_API_KEY    = os.getenv("RESEND_API_KEY", "")
RESEND_FROM       = os.getenv("RESEND_FROM", "DSA Planner <info@dsa-planner.co.in>")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
FRONTEND_URL      = os.getenv("FRONTEND_URL", "https://dsa-planner.co.in")


# ── Email via Resend ───────────────────────────────────────────────────────────

async def send_email(to_email: str, subject: str, body_html: str) -> bool:
    if not RESEND_API_KEY:
        log.warning("RESEND_API_KEY not set — skipping email to %s", to_email)
        return False
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "https://api.resend.com/emails",
                headers={"Authorization": f"Bearer {RESEND_API_KEY}"},
                json={
                    "from":    RESEND_FROM,
                    "to":      [to_email],
                    "subject": subject,
                    "html":    body_html,
                },
            )
        if r.status_code in (200, 201):
            log.info("Email sent via Resend to %s", to_email)
            return True
        log.error("Resend API error %s: %s", r.status_code, r.text)
        return False
    except Exception as e:
        log.error("Email send failed to %s: %s", to_email, e)
        return False


def _email_body(message: str) -> str:
    safe_msg = message.replace("<", "&lt;").replace(">", "&gt;")
    return f"""
<html><body style="font-family:Inter,sans-serif;background:#faf5ff;padding:32px;margin:0;">
<div style="max-width:500px;margin:0 auto;background:#fff;border-radius:16px;
            padding:32px;border:1.5px solid #ede9fe;
            box-shadow:0 4px 16px rgba(124,58,237,.08);">
  <div style="font-size:1.5em;font-weight:800;margin-bottom:6px;color:#3b0764;">
    🎯 DSA Revision Planner
  </div>
  <div style="width:40px;height:3px;background:linear-gradient(90deg,#7c3aed,#db2777);
              border-radius:2px;margin-bottom:20px;"></div>
  <p style="color:#374151;font-size:1.05em;line-height:1.7;margin:0 0 24px;">{safe_msg}</p>
  <a href="{FRONTEND_URL}"
     style="display:inline-block;padding:11px 26px;
            background:linear-gradient(135deg,#7c3aed,#db2777);
            color:#fff;border-radius:10px;text-decoration:none;
            font-weight:700;font-size:.95em;letter-spacing:.3px;">
    Open Planner →
  </a>
  <p style="color:#9ca3af;font-size:.75em;margin-top:28px;border-top:1px solid #f3e8ff;
            padding-top:14px;">
    You're receiving this because you enabled notifications in DSA Revision Planner.
  </p>
</div>
</body></html>"""


def _subject_for_type(notif_type: str) -> str:
    return {
        "revisions": "📚 DSA Planner — Revisions Due Today",
        "streak":    "🔥 DSA Planner — Don't Break Your Streak!",
        "mastery":   "🏆 DSA Planner — Mastery Update",
    }.get(notif_type, "🎯 DSA Revision Planner")


# ── Telegram ───────────────────────────────────────────────────────────────────

async def send_telegram(chat_id: str, message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN:
        log.warning("TELEGRAM_BOT_TOKEN not set — skipping Telegram")
        return False
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(url, json={
                "chat_id": chat_id,
                "text": message,
                "parse_mode": "Markdown",
            })
        if r.status_code == 200:
            log.info("Telegram sent to chat_id=%s", chat_id)
            return True
        log.warning("Telegram API returned %s for chat_id=%s: %s", r.status_code, chat_id, r.text)
        return False
    except Exception as e:
        log.error("Telegram send failed for chat_id=%s: %s", chat_id, e)
        return False


# ── In-app (DB) ────────────────────────────────────────────────────────────────

async def create_in_app(db, user_id: int, message: str, notif_type: str = "info") -> None:
    from backend.db.models import Notification
    notif = Notification(
        user_id=user_id,
        message=message,
        notif_type=notif_type,
        is_read=False,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    db.add(notif)
    await db.commit()


# ── Unified dispatch ───────────────────────────────────────────────────────────

async def notify_user(db, user, message: str, notif_type: str = "info") -> None:
    """Create in-app notification and dispatch to enabled external channels."""
    await create_in_app(db, user.id, message, notif_type)

    if getattr(user, "email_notif_enabled", False) and user.email:
        await send_email(user.email, _subject_for_type(notif_type), _email_body(message))

    if getattr(user, "telegram_notif_enabled", False) and getattr(user, "telegram_chat_id", None):
        await send_telegram(user.telegram_chat_id, message)
