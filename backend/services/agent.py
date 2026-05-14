"""
Agentic AI services using Claude tool-use loops (Path A).

Claude reasons across multiple tool calls — querying the real DB for context —
before producing output. This gives personalized, history-aware results
instead of generic prompt→response text.
"""

import json
import logging
import os
from datetime import datetime, timedelta, timezone

import anthropic

log = logging.getLogger(__name__)

MODEL = "claude-haiku-4-5-20251001"
MAX_ITERATIONS = 6  # Safety cap on agent loop turns


def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))


# ── DB tool implementations ─────────────────────────────────────────────────────

async def _tool_get_past_attempts(question_id: int, user_id: int) -> list:
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import PracticeLog
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(PracticeLog).where(
                PracticeLog.question_id == question_id,
                PracticeLog.user_id == user_id,
            ).order_by(PracticeLog.date)
        )).scalars().all()
        return [
            {
                "date": r.date,
                "correct": r.correct,
                "hint_used": r.hint_used,
                "time_taken_seconds": r.time_taken,
                "logic_preview": (r.logic or "")[:300],
                "code_preview": (r.code or "")[:300],
            }
            for r in rows
        ]


async def _tool_get_user_weak_areas(user_id: int) -> list:
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import UserQuestionProgress, Question
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(UserQuestionProgress, Question)
            .join(Question, UserQuestionProgress.question_id == Question.id)
            .where(
                UserQuestionProgress.user_id == user_id,
                UserQuestionProgress.accuracy.isnot(None),
            )
        )).all()

        pattern_data: dict[str, list] = {}
        for progress, question in rows:
            p = question.pattern or "Unknown"
            pattern_data.setdefault(p, []).append(progress.accuracy)

        result = []
        for pattern, accuracies in pattern_data.items():
            avg = sum(accuracies) / len(accuracies)
            result.append({
                "pattern": pattern,
                "avg_accuracy": round(avg, 1),
                "question_count": len(accuracies),
            })

        result.sort(key=lambda x: x["avg_accuracy"])
        return result[:10]


async def _tool_get_user_stats(user_id: int) -> dict:
    from backend.db.session import AsyncSessionLocal
    from backend.crud.question import get_activity

    async with AsyncSessionLocal() as db:
        stats = await get_activity(db, user_id)
        stats.pop("recent_sessions", None)
        stats.pop("sessions_by_date", None)
        return stats


async def _tool_get_due_questions(user_id: int, days_ahead: int = 3) -> list:
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import UserQuestionProgress, Question
    from sqlalchemy.future import select

    today = datetime.now(timezone.utc).date()
    cutoff = (today + timedelta(days=days_ahead)).isoformat()
    today_str = today.isoformat()

    async with AsyncSessionLocal() as db:
        rows = (await db.execute(
            select(UserQuestionProgress, Question)
            .join(Question, UserQuestionProgress.question_id == Question.id)
            .where(
                UserQuestionProgress.user_id == user_id,
                UserQuestionProgress.next_revision.isnot(None),
                UserQuestionProgress.next_revision <= cutoff,
            )
        )).all()

        result = []
        for progress, question in rows:
            result.append({
                "question_id": question.id,
                "title": question.title,
                "pattern": question.pattern,
                "difficulty": question.difficulty,
                "next_revision": progress.next_revision,
                "accuracy": progress.accuracy,
                "revision_status": progress.revision_status,
                "overdue": progress.next_revision < today_str,
            })

        result.sort(key=lambda x: (not x["overdue"], x["next_revision"]))
        return result


async def _tool_get_question_details(question_id: int) -> dict:
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import Question
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        q = (await db.execute(
            select(Question).where(Question.id == question_id)
        )).scalar_one_or_none()
        if not q:
            return {}
        return {
            "id": q.id,
            "title": q.title,
            "pattern": q.pattern,
            "category": q.category,
            "difficulty": q.difficulty,
        }


# ── Tool schemas for Claude API ─────────────────────────────────────────────────

_TOOL_SCHEMAS = [
    {
        "name": "get_past_attempts",
        "description": (
            "Get the student's previous practice attempts for a specific question. "
            "Shows history of correct/incorrect, time taken, and their approach/code."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question_id": {"type": "integer", "description": "The question ID"},
                "user_id": {"type": "integer", "description": "The user ID"},
            },
            "required": ["question_id", "user_id"],
        },
    },
    {
        "name": "get_user_weak_areas",
        "description": (
            "Get the DSA patterns where the student has the lowest average accuracy. "
            "Returns patterns sorted ascending by accuracy (weakest first)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "The user ID"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_user_stats",
        "description": (
            "Get the student's overall practice statistics: current streak, "
            "total sessions, time spent, and pattern breakdown."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "The user ID"},
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_due_questions",
        "description": (
            "Get questions due or coming up for revision within the next N days. "
            "Returns overdue questions first, then upcoming ones by date."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "user_id": {"type": "integer", "description": "The user ID"},
                "days_ahead": {
                    "type": "integer",
                    "description": "Days to look ahead (default 3)",
                    "default": 3,
                },
            },
            "required": ["user_id"],
        },
    },
    {
        "name": "get_question_details",
        "description": "Get details about a specific DSA question: title, pattern, category, difficulty.",
        "input_schema": {
            "type": "object",
            "properties": {
                "question_id": {"type": "integer", "description": "The question ID"},
            },
            "required": ["question_id"],
        },
    },
]


# ── Tool executor ────────────────────────────────────────────────────────────────

async def _execute_tool(name: str, inputs: dict):
    try:
        if name == "get_past_attempts":
            return await _tool_get_past_attempts(inputs["question_id"], inputs["user_id"])
        if name == "get_user_weak_areas":
            return await _tool_get_user_weak_areas(inputs["user_id"])
        if name == "get_user_stats":
            return await _tool_get_user_stats(inputs["user_id"])
        if name == "get_due_questions":
            return await _tool_get_due_questions(inputs["user_id"], inputs.get("days_ahead", 3))
        if name == "get_question_details":
            return await _tool_get_question_details(inputs["question_id"])
        return {"error": f"Unknown tool: {name}"}
    except Exception as e:
        log.warning("Tool %s failed: %s", name, e)
        return {"error": str(e)}


# ── Generic agent loop ───────────────────────────────────────────────────────────

async def _run_agent_loop(
    system: str,
    user_message: str,
    max_tokens: int = 1000,
) -> str:
    """
    Run a Claude tool-use agent loop.

    Claude receives the system prompt and user message, calls tools as needed,
    receives results, and continues until it produces a final text response.
    Returns the final text output.
    """
    client = _client()
    messages = [{"role": "user", "content": user_message}]

    for _ in range(MAX_ITERATIONS):
        response = await client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            tools=_TOOL_SCHEMAS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            return "\n".join(b.text for b in response.content if hasattr(b, "text"))

        if response.stop_reason == "tool_use":
            tool_uses = [b for b in response.content if b.type == "tool_use"]
            messages.append({"role": "assistant", "content": response.content})

            tool_results = []
            for tu in tool_uses:
                result = await _execute_tool(tu.name, tu.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tu.id,
                    "content": json.dumps(result, default=str),
                })
            messages.append({"role": "user", "content": tool_results})
        else:
            break

    # Fallback: extract any text produced before stopping
    text = "\n".join(b.text for b in response.content if hasattr(b, "text"))
    return text or ""


# ── Public agentic functions ─────────────────────────────────────────────────────

async def agentic_session_insight(session: dict, user_id: int) -> str:
    """
    Agent-powered session insight.

    Claude queries past attempts and the student's weak areas before writing
    the insight, producing personalized feedback that references their history
    instead of generic advice.
    """
    minutes = session.get("time_taken_seconds", 0) // 60
    seconds = session.get("time_taken_seconds", 0) % 60
    time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"
    question_id = session.get("question_id")

    system = (
        "You are an encouraging DSA coach writing a personalized practice insight. "
        "Before writing, use your tools to:\n"
        "1. Fetch past attempts for this question (use question_id and user_id from the session)\n"
        "2. Fetch the student's weak areas to understand where this question fits\n"
        "Use this real data to write a specific, history-aware insight — not generic advice. "
        "If they attempted this question before, reference whether they improved. "
        "If this pattern is a weak area, acknowledge it and encourage them."
    )

    q_id_line = f"Question ID: {question_id}" if question_id else "Question ID: (not provided)"
    user_message = (
        f"Write a short, motivating markdown insight (≤ 250 words) for this practice session.\n"
        f"{q_id_line}\n"
        f"User ID: {user_id}\n\n"
        f"Session details:\n"
        f"- Problem: {session.get('question')}\n"
        f"- Pattern: {session.get('pattern', 'Unknown')}\n"
        f"- Difficulty: {session.get('difficulty', 'Unknown')}\n"
        f"- Date: {session.get('date')}\n"
        f"- Correct: {'Yes' if session.get('correct') else 'No'}\n"
        f"- Time: {time_str}\n"
        f"- Logic: {session.get('logic') or '(not provided)'}\n\n"
        f"Format exactly:\n"
        f"# {session.get('question')} — {session.get('date')}\n\n"
        f"## Quick Stats\n"
        f"- ✅ Correct: {'Yes' if session.get('correct') else 'No'}\n"
        f"- ⏱️ Time: {time_str}\n"
        f"- 🧠 Pattern: {session.get('pattern', 'Unknown')}\n\n"
        f"## What went well\n"
        f"<1-2 sentences — reference their actual logic/history>\n\n"
        f"## To improve\n"
        f"<1-2 sentences — reference their specific code or recurring gaps>\n\n"
        f"## Key takeaway\n"
        f"<One sentence personalized to their journey with this problem>"
    )

    try:
        return await _run_agent_loop(system, user_message, max_tokens=700)
    except Exception as e:
        log.error("Agentic session insight failed, falling back: %s", e)
        from backend.services.ai_insights import generate_session_insight
        return await generate_session_insight(session)


async def agentic_weekly_summary(sessions: list[dict], username: str, user_id: int) -> str:
    """
    Agent-powered weekly summary.

    Claude queries weak areas and due questions before writing the summary,
    so recommendations are grounded in the student's actual data.
    """
    if not sessions:
        return ""

    today = datetime.now(timezone.utc)
    week_label = f"{today.year}-W{today.isocalendar()[1]:02d}"
    total_min = sum(s.get("time_taken_seconds", 0) for s in sessions) // 60
    correct_count = sum(1 for s in sessions if s.get("correct"))

    session_lines = "\n".join(
        f"- {s.get('date')} | {s.get('question')} | {s.get('pattern', '?')} | "
        f"{'✅' if s.get('correct') else '❌'} | {s.get('time_taken_seconds', 0) // 60}min"
        for s in sessions
    )

    system = (
        f"You are a DSA coach writing a weekly review for {username}. "
        "Use your tools to check their current weak areas and upcoming due questions — "
        "your recommendations must be specific and grounded in their data, not generic."
    )

    user_message = (
        f"Write an encouraging, data-driven markdown weekly summary (≤ 400 words).\n"
        f"User ID: {user_id}\n"
        f"Week: {week_label}\n\n"
        f"Sessions this week:\n{session_lines}\n\n"
        f"Stats: {len(sessions)} sessions, {total_min} total minutes, "
        f"{correct_count}/{len(sessions)} correct\n\n"
        f"First use get_user_weak_areas and get_due_questions, then write:\n\n"
        f"# Weekly Summary — {week_label}\n\n"
        f"## Stats\n"
        f"- Sessions: {len(sessions)}\n"
        f"- Total time: {total_min} min\n"
        f"- Accuracy: {round(correct_count / len(sessions) * 100)}%\n\n"
        f"## Strongest patterns this week\n<bullet points>\n\n"
        f"## Patterns needing attention\n<bullet points — cite your tool results>\n\n"
        f"## Recommendations for next week\n"
        f"<3 specific bullet points based on actual weak areas and due questions>\n\n"
        f"## Motivational note\n<One short, personal closing thought>"
    )

    try:
        return await _run_agent_loop(system, user_message, max_tokens=900)
    except Exception as e:
        log.error("Agentic weekly summary failed, falling back: %s", e)
        from backend.services.ai_insights import generate_weekly_summary
        return await generate_weekly_summary(sessions, username)


async def agentic_study_coach(user_id: int, username: str) -> str:
    """
    Autonomous study coach agent.

    Queries due questions, weak areas, and stats, then produces a concise,
    prioritized study plan notification for the day. Returns a 2-4 sentence
    notification string ready to send to the user.
    """
    system = (
        "You are an autonomous DSA study coach. "
        "Use your tools to understand the student's current state, then write a "
        "2-4 sentence personalized notification that:\n"
        "- Names 1-2 specific questions or patterns to focus on today\n"
        "- References their streak or recent accuracy to motivate them\n"
        "- Is specific and actionable, not generic\n"
        "If nothing is overdue, suggest proactively working on their weakest pattern."
    )

    user_message = (
        f"User ID: {user_id}\n"
        f"Username: {username}\n\n"
        "Use get_due_questions, get_user_weak_areas, and get_user_stats, "
        "then write a 2-4 sentence study plan notification for today."
    )

    try:
        return await _run_agent_loop(system, user_message, max_tokens=300)
    except Exception as e:
        log.error("Agentic study coach failed for user_id=%s: %s", user_id, e)
        return ""
