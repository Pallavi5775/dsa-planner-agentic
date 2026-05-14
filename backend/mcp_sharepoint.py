#!/usr/bin/env python3
"""
MCP server — SharePoint / OneDrive tools.

Exposes the user's DSA files stored in OneDrive via Microsoft Graph API
as MCP tools so Claude Code can read, search, and write them directly.

Add to .claude/settings.json:
  "sharepoint": {
    "command": "<venv>/python.exe",
    "args": ["DSA_TRACKER/backend/mcp_sharepoint.py"],
    "cwd": "<project-root>"
  }
"""

import os
import sys

_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _here not in sys.path:
    sys.path.insert(0, _here)

from dotenv import load_dotenv
load_dotenv(os.path.join(_here, "DSA_TRACKER", ".env"))
load_dotenv()

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "sharepoint",
    description="DSA Planner — OneDrive/SharePoint file tools via Microsoft Graph API",
)


def _svc(user_id: int):
    """Get SharePointStorageService for a user by loading their tokens from DB."""
    import asyncio
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from sqlalchemy.future import select
    from backend.services.sharepoint_storage import SharePointStorageService

    async def _load():
        async with AsyncSessionLocal() as db:
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user or not user.microsoft_access_token:
            return None
        return SharePointStorageService(user.microsoft_access_token, user.microsoft_refresh_token)

    return asyncio.get_event_loop().run_until_complete(_load())


@mcp.tool()
async def sharepoint_list_sessions(user_id: int) -> list[dict]:
    """
    List all DSA practice session JSON files stored in the user's OneDrive.

    Args:
        user_id: The user's numeric ID (must have Microsoft connected)
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from backend.services.sharepoint_storage import SharePointStorageService
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    if not user or not user.microsoft_access_token:
        return [{"error": f"User {user_id} has no Microsoft token connected"}]

    svc = SharePointStorageService(user.microsoft_access_token, user.microsoft_refresh_token)
    return await svc.list_session_files()


@mcp.tool()
async def sharepoint_list_sessions_with_insights(user_id: int) -> list[dict]:
    """
    List all DSA sessions paired with their AI insight markdown from OneDrive.

    Args:
        user_id: The user's numeric ID
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from backend.services.sharepoint_storage import SharePointStorageService
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    if not user or not user.microsoft_access_token:
        return [{"error": f"User {user_id} has no Microsoft token connected"}]

    svc = SharePointStorageService(user.microsoft_access_token, user.microsoft_refresh_token)
    return await svc.list_sessions_with_insights()


@mcp.tool()
async def sharepoint_save_session(user_id: int, session: dict) -> dict:
    """
    Save a practice session JSON file to the user's OneDrive.

    Args:
        user_id: The user's numeric ID
        session: Session data dict (question, date, correct, logic, code, etc.)
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from backend.services.sharepoint_storage import SharePointStorageService
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    if not user or not user.microsoft_access_token:
        return {"saved": False, "error": "No Microsoft token"}

    svc = SharePointStorageService(user.microsoft_access_token, user.microsoft_refresh_token)
    await svc.ensure_root_folder()
    ok = await svc.commit_session(session)
    return {"saved": ok}


@mcp.tool()
async def sharepoint_save_summary(user_id: int, summary_md: str, week_label: str) -> dict:
    """
    Save a weekly summary markdown file to the user's OneDrive.

    Args:
        user_id: The user's numeric ID
        summary_md: Markdown content of the summary
        week_label: Week identifier e.g. '2026-W20'
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from backend.services.sharepoint_storage import SharePointStorageService
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    if not user or not user.microsoft_access_token:
        return {"saved": False, "error": "No Microsoft token"}

    svc = SharePointStorageService(user.microsoft_access_token, user.microsoft_refresh_token)
    ok = await svc.commit_weekly_summary(summary_md, week_label)
    return {"saved": ok, "week_label": week_label}


@mcp.tool()
async def check_microsoft_connection(user_id: int) -> dict:
    """
    Check whether a user has Microsoft/OneDrive connected.

    Args:
        user_id: The user's numeric ID
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    if not user:
        return {"connected": False, "reason": "user_not_found"}
    return {
        "connected": bool(user.microsoft_access_token),
        "microsoft_user_id": user.microsoft_user_id,
        "has_teams_webhook": bool(user.teams_webhook_url),
    }


if __name__ == "__main__":
    mcp.run()
