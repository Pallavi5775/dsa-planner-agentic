"""
Microsoft OAuth routes.

Single callback URL for both flows — state parameter determines the action:
  state=login           → new login / create account
  state=connect:{uid}   → connect Microsoft to existing account

Only ONE redirect URI needed in Azure:
  http://localhost:8000/api/auth/microsoft/callback

Required env vars:
  MICROSOFT_CLIENT_ID
  MICROSOFT_CLIENT_SECRET
  MICROSOFT_TENANT_ID   (use "common" for personal + work accounts)
"""

import os
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.db.session import get_db
from backend.db.models import User
from backend.crud.user import get_or_create_oauth_user
from backend.core.security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

MS_CLIENT_ID     = os.getenv("MICROSOFT_CLIENT_ID", "")
MS_CLIENT_SECRET = os.getenv("MICROSOFT_CLIENT_SECRET", "")
MS_TENANT_ID     = os.getenv("MICROSOFT_TENANT_ID", "common")
BACKEND_URL      = os.getenv("BACKEND_URL",  "http://localhost:8000")
FRONTEND_URL     = os.getenv("FRONTEND_URL", "http://localhost:8501")

CALLBACK_URL = f"{BACKEND_URL}/api/auth/microsoft/callback"

MS_SCOPES = " ".join([
    "openid", "email", "profile", "offline_access",
    "Files.ReadWrite",
    "Calendars.ReadWrite",
    "ChannelMessage.Send",
])

_AUTH_URL  = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/authorize"
_TOKEN_URL = f"https://login.microsoftonline.com/{MS_TENANT_ID}/oauth2/v2.0/token"


def _redirect_to_frontend(user: User) -> RedirectResponse:
    token = create_access_token(user.id, user.username, user.role)
    return RedirectResponse(
        f"{FRONTEND_URL}?tok={token}&usr={user.username}&uid={user.id}&rol={user.role}"
    )


def _ms_auth_url(state: str) -> str:
    return (
        f"{_AUTH_URL}"
        f"?client_id={MS_CLIENT_ID}"
        f"&redirect_uri={quote(CALLBACK_URL, safe='')}"
        f"&response_type=code"
        f"&scope={quote(MS_SCOPES)}"
        f"&response_mode=query"
        f"&state={quote(state)}"
    )


async def _exchange_code(code: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            _TOKEN_URL,
            data={
                "client_id":     MS_CLIENT_ID,
                "client_secret": MS_CLIENT_SECRET,
                "code":          code,
                "grant_type":    "authorization_code",
                "redirect_uri":  CALLBACK_URL,
                "scope":         MS_SCOPES,
            },
        )
    data = r.json()
    if "error" in data:
        raise HTTPException(400, data.get("error_description", "Microsoft token exchange failed"))
    return data


async def _get_ms_profile(access_token: str) -> dict:
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://graph.microsoft.com/v1.0/me",
            headers={"Authorization": f"Bearer {access_token}"},
        )
    return r.json()


# ── Login (new or existing account) ───────────────────────────────────────────

@router.get("/microsoft")
async def microsoft_login():
    """Redirect to Microsoft login. Creates or logs in an account on callback."""
    if not MS_CLIENT_ID:
        raise HTTPException(500, "MICROSOFT_CLIENT_ID not configured")
    return RedirectResponse(_ms_auth_url("login"))


# ── Connect Microsoft to an existing logged-in account ─────────────────────────

@router.get("/microsoft/connect")
async def microsoft_connect(current: dict = Depends(get_current_user)):
    """
    Connect Microsoft to an already-logged-in account.
    Grants OneDrive + Calendar + Teams access without replacing the login.
    """
    if not MS_CLIENT_ID:
        raise HTTPException(500, "MICROSOFT_CLIENT_ID not configured")
    return RedirectResponse(_ms_auth_url(f"connect:{current['id']}"))


# ── Single shared callback ─────────────────────────────────────────────────────

@router.get("/microsoft/callback")
async def microsoft_callback(
    code: str,
    state: str = "login",
    db: AsyncSession = Depends(get_db),
):
    """
    Single callback for both login and connect flows.
    state=login          → create/login account
    state=connect:{uid}  → link Microsoft to existing account
    """
    try:
        token_data    = await _exchange_code(code)
        access_token  = token_data["access_token"]
        refresh_token = token_data.get("refresh_token", "")
        profile       = await _get_ms_profile(access_token)
        ms_id         = profile.get("id", "")
    except HTTPException as exc:
        return RedirectResponse(f"{FRONTEND_URL}?auth_error={quote(exc.detail)}")

    # ── Connect flow: link to existing account ─────────────────────────────────
    if state.startswith("connect:"):
        try:
            user_id = int(state.split(":", 1)[1])
        except (ValueError, IndexError):
            return RedirectResponse(f"{FRONTEND_URL}?auth_error=Invalid+state")

        user = (await db.execute(
            select(User).where(User.id == user_id)
        )).scalar_one_or_none()

        if not user:
            return RedirectResponse(f"{FRONTEND_URL}?auth_error=User+not+found")

        user.microsoft_access_token  = access_token
        user.microsoft_refresh_token = refresh_token
        user.microsoft_user_id       = ms_id
        await db.commit()

        return RedirectResponse(f"{FRONTEND_URL}?microsoft_connected=1")

    # ── Login flow: create or find account ────────────────────────────────────
    email = profile.get("mail") or profile.get("userPrincipalName", "")
    name  = profile.get("displayName") or (email.split("@")[0] if email else "user")

    if not email:
        return RedirectResponse(f"{FRONTEND_URL}?auth_error=Microsoft+email+not+available")

    try:
        user = await get_or_create_oauth_user(
            db,
            provider="microsoft",
            oauth_id=ms_id,
            email=email,
            username=name,
            avatar_url=None,
        )
    except HTTPException as exc:
        return RedirectResponse(f"{FRONTEND_URL}?auth_error={quote(exc.detail)}")

    user.microsoft_access_token  = access_token
    user.microsoft_refresh_token = refresh_token
    user.microsoft_user_id       = ms_id
    await db.commit()

    # Auto-provision DSA-Planner folder in OneDrive on first login
    try:
        from backend.services.sharepoint_storage import SharePointStorageService
        svc = SharePointStorageService(access_token, refresh_token)
        await svc.ensure_root_folder()
    except Exception:
        pass  # Non-blocking — folder created lazily on first upload if this fails

    return _redirect_to_frontend(user)
