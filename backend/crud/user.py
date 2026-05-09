import os
import re
from fastapi import HTTPException
from sqlalchemy.future import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import User


def _is_admin_email(email: str) -> bool:
    """Return True if email is in the ADMIN_EMAILS env var (comma-separated)."""
    raw = os.getenv("ADMIN_EMAILS", "")
    allowed = {e.strip().lower() for e in raw.split(",") if e.strip()}
    return email.lower() in allowed


def _sanitize_username(raw: str) -> str:
    """Replace non-alphanumeric characters and trim to 30 chars."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", raw).strip("_") or "user"
    return cleaned[:30]


async def _unique_username(db: AsyncSession, base: str) -> str:
    """Append an incrementing suffix until the username is not taken."""
    candidate = base
    counter = 1
    while True:
        result = await db.execute(select(User).where(User.username == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
        candidate = f"{base}{counter}"
        counter += 1


async def get_or_create_oauth_user(
    db: AsyncSession,
    *,
    provider: str,
    oauth_id: str,
    email: str,
    username: str,
    avatar_url: str | None = None,
) -> User:
    correct_role = "admin" if _is_admin_email(email) else "user"

    # 1. Exact match by provider + provider user-id (returning user)
    result = await db.execute(
        select(User).where(User.oauth_provider == provider, User.oauth_id == oauth_id)
    )
    user = result.scalar_one_or_none()
    if user:
        changed = False
        if avatar_url and user.avatar_url != avatar_url:
            user.avatar_url = avatar_url
            changed = True
        if user.role != correct_role:      # sync role if ADMIN_EMAILS list changed
            user.role = correct_role
            changed = True
        if changed:
            await db.commit()
            await db.refresh(user)
        return user

    # 2. Same email already in DB — only link if it's already a passwordless OAuth account.
    #    Legacy password-auth users (hashed_password set) are NOT auto-merged; the email
    #    gets a provider-scoped placeholder so both accounts coexist independently.
    result = await db.execute(select(User).where(User.email == email))
    existing = result.scalar_one_or_none()
    if existing:
        if existing.hashed_password is None:
            existing.oauth_provider = provider
            existing.oauth_id = oauth_id
            existing.role = correct_role
            if avatar_url:
                existing.avatar_url = avatar_url
            await db.commit()
            await db.refresh(existing)
            return existing
        else:
            email = f"{provider}_{oauth_id}@oauth.local"

    # 3. Brand-new user — only admins (or admin-pre-registered emails) may create accounts.
    #    Non-admin emails must be pre-registered by an admin via POST /api/users/.
    if not _is_admin_email(email):
        raise HTTPException(
            status_code=403,
            detail="Account creation is restricted. Ask an admin to create your account first.",
        )

    safe_username = await _unique_username(db, _sanitize_username(username))
    user = User(
        username=safe_username,
        email=email,
        hashed_password=None,
        oauth_provider=provider,
        oauth_id=oauth_id,
        avatar_url=avatar_url,
        role=correct_role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
