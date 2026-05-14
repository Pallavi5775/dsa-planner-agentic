"""
In-memory agent activity log.

All agents write here when they call tools. The frontend polls
/api/admin/agent-logs to display a live proof-of-execution panel.
"""

from collections import deque
from datetime import datetime, timezone

_buffer: deque = deque(maxlen=300)  # last 300 entries, auto-evicts oldest


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S")


def log_agent_start(agent: str, goal: str) -> None:
    _buffer.append({
        "time":   _now(),
        "agent":  agent,
        "type":   "start",
        "icon":   "🚀",
        "label":  f"Agent started",
        "detail": goal[:200],
    })


def log_tool_call(agent: str, tool: str, inputs: dict, step: int = 0) -> None:
    # Build a readable input summary
    if tool == "get_existing_titles":
        input_str = "checking existing questions in DB"
    elif tool == "get_existing_patterns":
        input_str = "fetching existing DSA patterns"
    elif tool == "get_past_attempts":
        input_str = f"question_id={inputs.get('question_id')}, user_id={inputs.get('user_id')}"
    elif tool == "get_user_weak_areas":
        input_str = f"user_id={inputs.get('user_id')}"
    elif tool == "get_user_stats":
        input_str = f"user_id={inputs.get('user_id')}"
    elif tool == "get_due_questions":
        input_str = f"user_id={inputs.get('user_id')}, days_ahead={inputs.get('days_ahead', 3)}"
    elif tool == "add_question":
        input_str = f"\"{inputs.get('title')}\" → {inputs.get('pattern')} / {inputs.get('difficulty')}"
    else:
        parts = [f"{k}={repr(v)[:30]}" for k, v in inputs.items()]
        input_str = ", ".join(parts[:3])

    _buffer.append({
        "time":   _now(),
        "agent":  agent,
        "type":   "tool_call",
        "icon":   "🔧",
        "step":   step,
        "label":  f"→ {tool}()",
        "detail": input_str,
    })


def log_tool_result(agent: str, tool: str, result: dict, step: int = 0) -> None:
    is_error = "error" in result

    if is_error:
        icon   = "❌"
        detail = f"ERROR: {result['error'][:150]}"
    elif tool == "get_existing_titles":
        count  = len(result.get("titles", []))
        icon   = "📋"
        detail = f"Found {count} existing questions"
    elif tool == "get_existing_patterns":
        patterns = result.get("patterns", [])
        icon     = "🏷"
        detail   = f"Found {len(patterns)} patterns: {', '.join(patterns[:5])}{'…' if len(patterns) > 5 else ''}"
    elif tool == "add_question":
        status = result.get("status")
        icon   = "✅" if status == "added" else "⏭" if status == "duplicate" else "⚠️"
        detail = "Added to database" if status == "added" else "Already exists — skipped"
    elif tool == "get_past_attempts":
        count  = len(result) if isinstance(result, list) else 0
        icon   = "📖"
        detail = f"Found {count} past attempt{'s' if count != 1 else ''}"
    elif tool == "get_user_weak_areas":
        count  = len(result) if isinstance(result, list) else 0
        icon   = "📊"
        detail = f"Found {count} weak pattern{'s' if count != 1 else ''}"
    elif tool == "get_due_questions":
        count  = len(result) if isinstance(result, list) else 0
        icon   = "📅"
        detail = f"{count} question{'s' if count != 1 else ''} due for revision"
    elif tool == "get_user_stats":
        icon   = "📈"
        detail = f"streak={result.get('streak_days',0)} days, total={result.get('total_sessions',0)} sessions"
    else:
        icon   = "↩"
        detail = str(result)[:120]

    _buffer.append({
        "time":   _now(),
        "agent":  agent,
        "type":   "tool_result",
        "icon":   icon,
        "step":   step,
        "label":  f"← {tool} result",
        "detail": detail,
        "is_error": is_error,
    })


def log_agent_end(agent: str, summary: str) -> None:
    _buffer.append({
        "time":   _now(),
        "agent":  agent,
        "type":   "end",
        "icon":   "✅",
        "label":  "Agent finished",
        "detail": summary[:200] if summary else "Done",
    })


def get_logs(limit: int = 100) -> list:
    entries = list(_buffer)
    return entries[-limit:]


def clear_logs() -> None:
    _buffer.clear()
