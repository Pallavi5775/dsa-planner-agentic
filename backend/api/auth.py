import os
import httpx
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.session import get_db
from backend.crud.user import get_or_create_oauth_user
from backend.core.security import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

GOOGLE_CLIENT_ID     = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
GITHUB_CLIENT_ID     = os.getenv("GITHUB_CLIENT_ID", "")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "")
BACKEND_URL          = os.getenv("BACKEND_URL",  "http://localhost:8000")
FRONTEND_URL         = os.getenv("FRONTEND_URL", "http://localhost:8501")


def _redirect_to_frontend(user) -> RedirectResponse:
    token = create_access_token(user.id, user.username, user.role)
    return RedirectResponse(
        f"{FRONTEND_URL}?tok={token}&usr={user.username}&uid={user.id}&rol={user.role}"
    )


# ── Google ─────────────────────────────────────────────────────────────────────

@router.get("/google")
async def google_login():
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(500, "GOOGLE_CLIENT_ID not configured")
    callback = f"{BACKEND_URL}/api/auth/google/callback"
    url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={GOOGLE_CLIENT_ID}"
        f"&redirect_uri={callback}"
        "&response_type=code"
        "&scope=openid+email+profile"
    )
    return RedirectResponse(url)


@router.get("/google/callback")
async def google_callback(code: str, db: AsyncSession = Depends(get_db)):
    callback = f"{BACKEND_URL}/api/auth/google/callback"
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "client_id":     GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "code":          code,
                "grant_type":    "authorization_code",
                "redirect_uri":  callback,
            },
        )
        token_data = token_resp.json()
        if "error" in token_data:
            raise HTTPException(400, token_data.get("error_description", "Google token exchange failed"))

        info_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token_data['access_token']}"},
        )
        info = info_resp.json()

    user = await get_or_create_oauth_user(
        db,
        provider="google",
        oauth_id=info["sub"],
        email=info["email"],
        username=info.get("name") or info["email"].split("@")[0],
        avatar_url=info.get("picture"),
    )
    return _redirect_to_frontend(user)


# ── GitHub ─────────────────────────────────────────────────────────────────────

@router.get("/github")
async def github_login():
    if not GITHUB_CLIENT_ID:
        raise HTTPException(500, "GITHUB_CLIENT_ID not configured")
    callback = f"{BACKEND_URL}/api/auth/github/callback"
    url = (
        "https://github.com/login/oauth/authorize"
        f"?client_id={GITHUB_CLIENT_ID}"
        f"&redirect_uri={callback}"
        "&scope=user:email"
    )
    return RedirectResponse(url)


@router.get("/github/callback")
async def github_callback(code: str, db: AsyncSession = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id":     GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code":          code,
            },
            headers={"Accept": "application/json"},
        )
        token_data = token_resp.json()
        if "error" in token_data:
            raise HTTPException(400, token_data.get("error_description", "GitHub token exchange failed"))
        access_token = token_data["access_token"]

        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
        gh_user = user_resp.json()

        # Fetch primary email if the profile email is private
        email = gh_user.get("email")
        if not email:
            emails_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
            )
            primary = next((e for e in emails_resp.json() if e.get("primary")), None)
            email = primary["email"] if primary else f"gh_{gh_user['id']}@users.noreply.github.com"

    user = await get_or_create_oauth_user(
        db,
        provider="github",
        oauth_id=str(gh_user["id"]),
        email=email,
        username=gh_user.get("login") or email.split("@")[0],
        avatar_url=gh_user.get("avatar_url"),
    )
    return _redirect_to_frontend(user)


# ── Session ────────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(current: dict = Depends(get_current_user)):
    return current
