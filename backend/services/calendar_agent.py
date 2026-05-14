"""
Outlook Calendar Scheduler Agent.

Uses Microsoft Graph Calendar API to:
- Find free time slots in the user's Outlook calendar
- Create study block events
- Update or reschedule missed revision sessions
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import anthropic
import httpx

log = logging.getLogger(__name__)
MODEL = "claude-haiku-4-5-20251001"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


def _graph_headers(access_token: str) -> dict:
    return {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}


# ── Graph API helpers ───────────────────────────────────────────────────────────

async def get_calendar_events(access_token: str, days: int = 7) -> list[dict]:
    """Fetch upcoming calendar events from Outlook."""
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=days)
    params = {
        "$select": "subject,start,end,isAllDay",
        "$orderby": "start/dateTime",
        "startDateTime": now.isoformat(),
        "endDateTime": end.isoformat(),
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.get(
                f"{GRAPH_BASE}/me/calendarView",
                headers=_graph_headers(access_token),
                params=params,
            )
        if r.status_code == 200:
            return r.json().get("value", [])
        log.warning("Calendar events fetch failed: %s", r.status_code)
        return []
    except Exception as e:
        log.error("Calendar events error: %s", e)
        return []


async def create_calendar_event(
    access_token: str,
    subject: str,
    start_iso: str,
    end_iso: str,
    body: str = "",
) -> dict:
    """Create a study block event in Outlook calendar."""
    payload = {
        "subject": subject,
        "body": {"contentType": "text", "content": body},
        "start": {"dateTime": start_iso, "timeZone": "UTC"},
        "end": {"dateTime": end_iso, "timeZone": "UTC"},
        "categories": ["DSA Study"],
        "isReminderOn": True,
        "reminderMinutesBeforeStart": 15,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                f"{GRAPH_BASE}/me/calendar/events",
                json=payload,
                headers=_graph_headers(access_token),
            )
        if r.status_code in (200, 201):
            ev = r.json()
            return {"id": ev["id"], "subject": ev["subject"], "start": ev["start"]["dateTime"]}
        log.warning("Create event failed: %s %s", r.status_code, r.text[:200])
        return {"error": r.text[:200]}
    except Exception as e:
        log.error("Create event error: %s", e)
        return {"error": str(e)}


# ── Agent ───────────────────────────────────────────────────────────────────────

async def run_calendar_scheduler(
    user_id: int,
    access_token: str,
    due_questions: list[dict],
    preferred_duration_minutes: int = 60,
) -> str:
    """
    Calendar Scheduler Agent.

    Looks at upcoming calendar events and due questions, finds free time slots,
    and creates study block events in Outlook. Returns a summary of what was scheduled.
    """
    tools = [
        {
            "name": "get_upcoming_events",
            "description": "Get the user's upcoming Outlook calendar events for the next N days.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "days": {"type": "integer", "default": 5},
                },
                "required": [],
            },
        },
        {
            "name": "create_study_block",
            "description": "Create a study session block in the user's Outlook calendar.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string", "description": "Event title, e.g. 'DSA Study — Two Pointers'"},
                    "start_iso": {"type": "string", "description": "Start datetime in ISO 8601 UTC format"},
                    "end_iso": {"type": "string", "description": "End datetime in ISO 8601 UTC format"},
                    "body": {"type": "string", "description": "Event description / questions to cover"},
                },
                "required": ["subject", "start_iso", "end_iso"],
            },
        },
    ]

    async def execute(name: str, inputs: dict) -> dict:
        try:
            if name == "get_upcoming_events":
                events = await get_calendar_events(access_token, inputs.get("days", 5))
                simplified = [
                    {
                        "subject": e.get("subject"),
                        "start": e.get("start", {}).get("dateTime"),
                        "end": e.get("end", {}).get("dateTime"),
                    }
                    for e in events
                ]
                return {"events": simplified}
            if name == "create_study_block":
                return await create_calendar_event(
                    access_token,
                    inputs["subject"],
                    inputs["start_iso"],
                    inputs["end_iso"],
                    inputs.get("body", ""),
                )
            return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            log.warning("Calendar tool %s failed: %s", name, e)
            return {"error": str(e)}

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    due_summary = json.dumps(due_questions[:10], default=str)

    client = _client()
    system = (
        "You are a calendar scheduling agent for a DSA student. "
        "Check their upcoming calendar events, find free slots, and create "
        "study block events for their due revision questions. "
        "Prefer morning or evening slots. Each block should be "
        f"{preferred_duration_minutes} minutes. "
        "Report what you scheduled."
    )
    user_message = (
        f"Current time: {today}\n"
        f"Due questions: {due_summary}\n\n"
        "Check the calendar, find a free slot, and schedule a study block."
    )
    messages = [{"role": "user", "content": user_message}]

    for _ in range(5):
        resp = await client.messages.create(
            model=MODEL, max_tokens=500, system=system,
            tools=tools, messages=messages,
        )
        if resp.stop_reason == "end_turn":
            return "\n".join(b.text for b in resp.content if hasattr(b, "text"))
        if resp.stop_reason == "tool_use":
            tool_uses = [b for b in resp.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": resp.content})
            results = []
            for tu in tool_uses:
                result = await execute(tu.name, tu.input)
                results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, default=str),
                })
            messages.append({"role": "user", "content": results})
        else:
            break

    return "Calendar scheduling complete."
