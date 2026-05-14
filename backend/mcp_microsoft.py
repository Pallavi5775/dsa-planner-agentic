#!/usr/bin/env python3
"""
MCP server — Microsoft Graph API tools (Calendar, Teams, OneDrive).

Exposes Outlook Calendar, Teams webhooks, and Graph API operations
as MCP tools so Claude Code can schedule events, send notifications,
and orchestrate multi-agent pipelines directly.

Add to .claude/settings.json:
  "microsoft-graph": {
    "command": "<venv>/python.exe",
    "args": ["DSA_TRACKER/backend/mcp_microsoft.py"],
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
    "microsoft-graph",
    description="Microsoft Graph API — Calendar events, Teams notifications, user profile",
)


async def _get_user_tokens(user_id: int) -> tuple[str | None, str | None, str | None]:
    """Return (access_token, refresh_token, teams_webhook_url) for a user."""
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()

    if not user:
        return None, None, None
    return user.microsoft_access_token, user.microsoft_refresh_token, user.teams_webhook_url


# ── Calendar tools ──────────────────────────────────────────────────────────────

@mcp.tool()
async def get_calendar_events(user_id: int, days_ahead: int = 7) -> list[dict]:
    """
    Get upcoming Outlook calendar events for a user.

    Args:
        user_id: The user's numeric ID (must have Microsoft connected)
        days_ahead: How many days ahead to fetch (default 7)
    """
    access_token, _, _ = await _get_user_tokens(user_id)
    if not access_token:
        return [{"error": f"User {user_id} has no Microsoft token"}]

    from backend.services.calendar_agent import get_calendar_events as _get
    events = await _get(access_token, days_ahead)
    return [
        {
            "subject": e.get("subject"),
            "start": e.get("start", {}).get("dateTime"),
            "end": e.get("end", {}).get("dateTime"),
            "is_all_day": e.get("isAllDay", False),
        }
        for e in events
    ]


@mcp.tool()
async def create_study_event(
    user_id: int,
    subject: str,
    start_iso: str,
    end_iso: str,
    description: str = "",
) -> dict:
    """
    Create a study block event in the user's Outlook calendar.

    Args:
        user_id: The user's numeric ID
        subject: Event title (e.g. 'DSA Study — Two Pointers')
        start_iso: Start datetime ISO 8601 UTC (e.g. '2026-05-15T09:00:00')
        end_iso: End datetime ISO 8601 UTC (e.g. '2026-05-15T10:00:00')
        description: Optional event body / questions to cover
    """
    access_token, _, _ = await _get_user_tokens(user_id)
    if not access_token:
        return {"error": f"User {user_id} has no Microsoft token"}

    from backend.services.calendar_agent import create_calendar_event
    return await create_calendar_event(access_token, subject, start_iso, end_iso, description)


@mcp.tool()
async def run_calendar_scheduler_for_user(user_id: int) -> str:
    """
    Run the Calendar Scheduler Agent for a user.

    The agent checks their Outlook calendar, finds free slots, and automatically
    creates study block events for due revision questions.

    Args:
        user_id: The user's numeric ID
    """
    access_token, _, _ = await _get_user_tokens(user_id)
    if not access_token:
        return f"User {user_id} has no Microsoft token connected."

    from backend.services.agent import _tool_get_due_questions
    from backend.services.calendar_agent import run_calendar_scheduler

    due = await _tool_get_due_questions(user_id, days_ahead=7)
    return await run_calendar_scheduler(user_id, access_token, due)


# ── Teams tools ─────────────────────────────────────────────────────────────────

@mcp.tool()
async def send_teams_notification(user_id: int, message: str, title: str = "DSA Planner") -> dict:
    """
    Send a notification to the user's Microsoft Teams channel via their webhook.

    Args:
        user_id: The user's numeric ID (must have teams_webhook_url configured)
        message: The message to send
        title: Optional card title (default 'DSA Planner')
    """
    _, _, webhook_url = await _get_user_tokens(user_id)
    if not webhook_url:
        return {"sent": False, "reason": "No teams_webhook_url configured for this user"}

    from backend.services.teams_agent import send_teams_webhook
    ok = await send_teams_webhook(webhook_url, message, title)
    return {"sent": ok}


@mcp.tool()
async def run_teams_notifier_for_user(user_id: int, message: str) -> str:
    """
    Run the Teams Notifier Agent for a user.

    The agent formats the message as a rich Teams card and dispatches it.

    Args:
        user_id: The user's numeric ID
        message: Raw message to format and send
    """
    access_token, _, webhook_url = await _get_user_tokens(user_id)
    if not webhook_url and not access_token:
        return "No Teams delivery method configured."

    from backend.services.teams_agent import run_teams_notifier
    return await run_teams_notifier(message=message, webhook_url=webhook_url, access_token=access_token)


# ── Orchestrator tools ──────────────────────────────────────────────────────────

@mcp.tool()
async def run_weekly_review(user_id: int, schedule_calendar: bool = False) -> dict:
    """
    Run the full weekly review pipeline for a user.

    Orchestrates: Study Coach + Weekly Summary (parallel) →
    SharePoint save + Teams notify + Calendar schedule (parallel fan-out).

    Args:
        user_id: The user's numeric ID
        schedule_calendar: Whether to also schedule next week's sessions in Outlook
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User, PracticeLog
    from backend.services.orchestrator import run_weekly_review_pipeline
    from sqlalchemy.future import select
    from datetime import datetime, timedelta, timezone

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            return {"error": f"User {user_id} not found"}

        today = datetime.now(timezone.utc).date()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
        logs = (await db.execute(
            select(PracticeLog).where(
                PracticeLog.user_id == user_id,
                PracticeLog.date >= week_start,
            )
        )).scalars().all()

    sessions = [
        {"date": l.date, "correct": l.correct, "time_taken_seconds": l.time_taken}
        for l in logs
    ]

    return await run_weekly_review_pipeline(
        user_id=user_id,
        username=user.username,
        sessions=sessions,
        ms_access_token=user.microsoft_access_token,
        ms_refresh_token=user.microsoft_refresh_token,
        teams_webhook=user.teams_webhook_url,
        schedule_calendar=schedule_calendar,
    )


@mcp.tool()
async def run_daily_coaching(user_id: int, schedule_calendar: bool = False) -> dict:
    """
    Run the daily coaching pipeline for a user.

    Orchestrates: Study Coach + due questions (parallel) →
    Calendar scheduling + Teams notification.

    Args:
        user_id: The user's numeric ID
        schedule_calendar: Whether to schedule today's study session in Outlook
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from backend.services.orchestrator import run_daily_coaching_pipeline
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
        if not user:
            return {"error": f"User {user_id} not found"}

    return await run_daily_coaching_pipeline(
        user_id=user_id,
        username=user.username,
        ms_access_token=user.microsoft_access_token,
        ms_refresh_token=user.microsoft_refresh_token,
        teams_webhook=user.teams_webhook_url,
        schedule_calendar=schedule_calendar,
    )


if __name__ == "__main__":
    mcp.run()
