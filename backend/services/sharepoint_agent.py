"""
SharePoint Librarian Agent.

Manages the user's DSA knowledge base in OneDrive/SharePoint.
Uses the Graph API to search, organize, and retrieve stored files.
"""

import json
import logging
import os
from datetime import datetime, timezone

import anthropic

from backend.services.sharepoint_storage import SharePointStorageService

log = logging.getLogger(__name__)
MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── Tool implementations ────────────────────────────────────────────────────────

async def _tool_list_sessions(access_token: str, refresh_token: str) -> list:
    svc = SharePointStorageService(access_token, refresh_token)
    return await svc.list_session_files()


async def _tool_list_sessions_with_insights(access_token: str, refresh_token: str) -> list:
    svc = SharePointStorageService(access_token, refresh_token)
    return await svc.list_sessions_with_insights()


async def _tool_save_session(access_token: str, refresh_token: str, session: dict) -> bool:
    svc = SharePointStorageService(access_token, refresh_token)
    await svc.ensure_root_folder()
    return await svc.commit_session(session)


async def _tool_save_insight(
    access_token: str, refresh_token: str,
    insight_md: str, date: str, question_title: str,
) -> bool:
    svc = SharePointStorageService(access_token, refresh_token)
    return await svc.commit_insight(insight_md, date, question_title)


async def _tool_save_weekly_summary(
    access_token: str, refresh_token: str,
    summary_md: str, week_label: str,
) -> bool:
    svc = SharePointStorageService(access_token, refresh_token)
    return await svc.commit_weekly_summary(summary_md, week_label)


# ── Agent loop ──────────────────────────────────────────────────────────────────

async def run_sharepoint_librarian(
    user_id: int,
    access_token: str,
    refresh_token: str,
    goal: str,
    extra_context: dict | None = None,
) -> str:
    """
    Run the SharePoint Librarian agent to manage files in OneDrive.

    The agent can list, save, and organize DSA session files and summaries.
    Returns a status/summary string.
    """
    tools = [
        {
            "name": "list_sessions",
            "description": "List all practice session JSON files stored in SharePoint/OneDrive.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "list_sessions_with_insights",
            "description": "List all sessions with their associated AI insight markdown.",
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
        {
            "name": "save_session",
            "description": "Save a practice session JSON file to SharePoint.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "session": {"type": "object", "description": "Session data dict"},
                },
                "required": ["session"],
            },
        },
        {
            "name": "save_insight",
            "description": "Save an AI insight markdown file to SharePoint.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "insight_md": {"type": "string"},
                    "date": {"type": "string"},
                    "question_title": {"type": "string"},
                },
                "required": ["insight_md", "date", "question_title"],
            },
        },
        {
            "name": "save_weekly_summary",
            "description": "Save a weekly summary markdown file to SharePoint.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "summary_md": {"type": "string"},
                    "week_label": {"type": "string", "description": "e.g. '2026-W20'"},
                },
                "required": ["summary_md", "week_label"],
            },
        },
    ]

    async def execute(name: str, inputs: dict):
        try:
            if name == "list_sessions":
                return await _tool_list_sessions(access_token, refresh_token)
            if name == "list_sessions_with_insights":
                return await _tool_list_sessions_with_insights(access_token, refresh_token)
            if name == "save_session":
                return await _tool_save_session(access_token, refresh_token, inputs["session"])
            if name == "save_insight":
                return await _tool_save_insight(
                    access_token, refresh_token,
                    inputs["insight_md"], inputs["date"], inputs["question_title"],
                )
            if name == "save_weekly_summary":
                return await _tool_save_weekly_summary(
                    access_token, refresh_token,
                    inputs["summary_md"], inputs["week_label"],
                )
            return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            log.warning("SharePoint tool %s failed: %s", name, e)
            return {"error": str(e)}

    context_str = json.dumps(extra_context or {}, default=str)
    client = _client()
    messages = [{"role": "user", "content": f"Goal: {goal}\nContext: {context_str}"}]
    system = (
        "You are the SharePoint Librarian for a DSA learning platform. "
        "Use your tools to manage files in the user's OneDrive/SharePoint storage. "
        "Complete the goal efficiently and report what you did."
    )

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

    return "\n".join(b.text for b in resp.content if hasattr(b, "text"))
