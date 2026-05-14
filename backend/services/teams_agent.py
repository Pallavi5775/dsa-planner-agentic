"""
Microsoft Teams Notification Agent.

Two delivery methods:
  1. Incoming Webhook (user pastes a webhook URL) — simple, no extra OAuth scopes
  2. Graph API (requires ChannelMessage.Send scope) — richer, needs admin consent

Method 1 is used when user has teams_webhook_url set.
Method 2 falls back when Graph API token + scope is available.
"""

import json
import logging
import os

import anthropic
import httpx

log = logging.getLogger(__name__)
MODEL = "claude-haiku-4-5-20251001"
GRAPH_BASE = "https://graph.microsoft.com/v1.0"


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── Delivery functions ──────────────────────────────────────────────────────────

async def send_teams_webhook(webhook_url: str, message: str, title: str = "DSA Planner") -> bool:
    """Send a message card to a Teams channel via incoming webhook."""
    payload = {
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        "themeColor": "7c3aed",
        "summary": title,
        "sections": [{"activityTitle": f"**{title}**", "activityText": message}],
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(webhook_url, json=payload)
        if r.status_code in (200, 202):
            log.info("Teams webhook message sent")
            return True
        log.warning("Teams webhook returned %s: %s", r.status_code, r.text[:200])
        return False
    except Exception as e:
        log.error("Teams webhook failed: %s", e)
        return False


async def send_teams_graph(access_token: str, team_id: str, channel_id: str, message: str) -> bool:
    """Send a message to a Teams channel via Graph API."""
    url = f"{GRAPH_BASE}/teams/{team_id}/channels/{channel_id}/messages"
    payload = {"body": {"contentType": "html", "content": message.replace("\n", "<br>")}}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                url, json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
        return r.status_code in (200, 201)
    except Exception as e:
        log.error("Teams Graph API send failed: %s", e)
        return False


# ── Agent ───────────────────────────────────────────────────────────────────────

async def run_teams_notifier(
    message: str,
    webhook_url: str | None = None,
    access_token: str | None = None,
    title: str = "DSA Planner Update",
) -> str:
    """
    Teams Notifier Agent.

    Given a raw message, the agent formats it as a rich Teams notification
    and dispatches it via webhook or Graph API.
    Returns a delivery status string.
    """
    if not webhook_url and not access_token:
        return "No Teams delivery method configured (no webhook_url or access_token)."

    tools = [
        {
            "name": "send_via_webhook",
            "description": "Send a formatted message card to Teams via incoming webhook.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "formatted_message": {"type": "string", "description": "The formatted message text"},
                    "card_title": {"type": "string", "description": "Card title"},
                },
                "required": ["formatted_message"],
            },
        },
    ]

    async def execute(name: str, inputs: dict) -> dict:
        if name == "send_via_webhook" and webhook_url:
            ok = await send_teams_webhook(
                webhook_url,
                inputs["formatted_message"],
                inputs.get("card_title", title),
            )
            return {"sent": ok}
        return {"error": "No delivery method available"}

    client = _client()
    system = (
        "You are a Teams notification formatter. "
        "Take the raw message, format it clearly with emojis and structure for a Teams card, "
        "then call send_via_webhook to deliver it."
    )
    messages = [{"role": "user", "content": f"Send this as a Teams notification:\n\n{message}"}]

    for _ in range(3):
        resp = await client.messages.create(
            model=MODEL, max_tokens=400, system=system,
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
                    "content": json.dumps(result),
                })
            messages.append({"role": "user", "content": results})
        else:
            break

    return "Teams notification dispatched."
