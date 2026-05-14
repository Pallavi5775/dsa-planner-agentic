#!/usr/bin/env python3
"""
MCP server for DSA Revision Planner (Path B).

Exposes the app's database and functions as MCP tools so Claude Code
(or any MCP client) can query real data and take actions interactively.

Setup — add to .claude/settings.json:
  {
    "mcpServers": {
      "dsa-planner": {
        "command": "python",
        "args": ["DSA_TRACKER/backend/mcp_server.py"],
        "cwd": "<absolute-path-to-agentic_version_dsaplanner>"
      }
    }
  }

Then in Claude Code you can ask:
  "What questions are due for user 1 today?"
  "Show me user 1's weak areas"
  "Get the practice history for question 5, user 1"
"""

import os
import sys
from datetime import datetime, timedelta, timezone

# Add DSA_TRACKER to path so "from backend.X import Y" works
_here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _here not in sys.path:
    sys.path.insert(0, _here)

from dotenv import load_dotenv

# Load .env from DSA_TRACKER directory
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)
load_dotenv()  # Also try CWD

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "dsa-planner",
    description="DSA Revision Planner — query questions, user progress, practice history, and stats",
)


# ── Tools ────────────────────────────────────────────────────────────────────────

@mcp.tool()
async def get_due_questions(user_id: int, days_ahead: int = 3) -> list[dict]:
    """
    Get questions due for revision for a user within the next N days.
    Returns overdue questions first, then upcoming ones sorted by date.

    Args:
        user_id: The user's numeric ID
        days_ahead: How many days forward to look (default 3)
    """
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

        result = [
            {
                "question_id": q.id,
                "title": q.title,
                "pattern": q.pattern,
                "difficulty": q.difficulty,
                "next_revision": p.next_revision,
                "accuracy": p.accuracy,
                "revision_status": p.revision_status,
                "overdue": p.next_revision < today_str,
            }
            for p, q in rows
        ]
        result.sort(key=lambda x: (not x["overdue"], x["next_revision"]))
        return result


@mcp.tool()
async def get_user_stats(user_id: int) -> dict:
    """
    Get overall practice statistics for a user: streak, total sessions,
    time spent, pattern breakdown, and today's activity.

    Args:
        user_id: The user's numeric ID
    """
    from backend.db.session import AsyncSessionLocal
    from backend.crud.question import get_activity

    async with AsyncSessionLocal() as db:
        stats = await get_activity(db, user_id)
        stats.pop("recent_sessions", None)
        stats.pop("sessions_by_date", None)
        return stats


@mcp.tool()
async def get_weak_areas(user_id: int, threshold: float = 80.0) -> list[dict]:
    """
    Get DSA patterns where the user's average accuracy is below a threshold.
    Returns patterns sorted ascending by accuracy (weakest first).

    Args:
        user_id: The user's numeric ID
        threshold: Accuracy percentage below which a pattern is considered weak (default 80)
    """
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
            if avg < threshold:
                result.append({
                    "pattern": pattern,
                    "avg_accuracy": round(avg, 1),
                    "question_count": len(accuracies),
                    "min_accuracy": round(min(accuracies), 1),
                })

        result.sort(key=lambda x: x["avg_accuracy"])
        return result


@mcp.tool()
async def get_past_attempts(question_id: int, user_id: int) -> list[dict]:
    """
    Get the full practice history for a specific question and user.
    Shows all attempts with dates, correctness, time taken, and their approach.

    Args:
        question_id: The question's numeric ID
        user_id: The user's numeric ID
    """
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
                "logic": r.logic or "",
                "code": (r.code or "")[:600],
            }
            for r in rows
        ]


@mcp.tool()
async def get_all_questions(
    pattern: str | None = None,
    difficulty: str | None = None,
) -> list[dict]:
    """
    Get all DSA questions in the system, optionally filtered by pattern or difficulty.

    Args:
        pattern: Filter by DSA pattern (e.g. "Two Pointers", "Sliding Window")
        difficulty: Filter by difficulty ("Easy", "Medium", "Hard")
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import Question
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        query = select(Question)
        if pattern:
            query = query.where(Question.pattern == pattern)
        if difficulty:
            query = query.where(Question.difficulty == difficulty)

        questions = (await db.execute(query)).scalars().all()
        return [
            {
                "id": q.id,
                "title": q.title,
                "pattern": q.pattern,
                "category": q.category,
                "difficulty": q.difficulty,
                "hint": q.hint,
            }
            for q in questions
        ]


@mcp.tool()
async def get_user_progress(user_id: int, pattern: str | None = None) -> list[dict]:
    """
    Get a user's progress across questions: coverage status, revision status,
    accuracy, next revision date, and SRS interval.

    Args:
        user_id: The user's numeric ID
        pattern: Optional — filter by DSA pattern
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import UserQuestionProgress, Question
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        query = (
            select(UserQuestionProgress, Question)
            .join(Question, UserQuestionProgress.question_id == Question.id)
            .where(UserQuestionProgress.user_id == user_id)
        )
        if pattern:
            query = query.where(Question.pattern == pattern)

        rows = (await db.execute(query)).all()
        return [
            {
                "question_id": q.id,
                "title": q.title,
                "pattern": q.pattern,
                "difficulty": q.difficulty,
                "coverage_status": p.coverage_status,
                "revision_status": p.revision_status,
                "accuracy": p.accuracy,
                "next_revision": p.next_revision,
                "interval_days": p.interval_days,
                "suggestions": (p.suggestions or "")[:300],
            }
            for p, q in rows
        ]


@mcp.tool()
async def get_pattern_notes(user_id: int, pattern: str | None = None) -> dict:
    """
    Get a user's notes and memory techniques for DSA patterns.

    Args:
        user_id: The user's numeric ID
        pattern: Optional — get notes for a specific pattern only
    """
    from backend.db.session import AsyncSessionLocal
    from backend.crud.question import get_all_pattern_notes

    async with AsyncSessionLocal() as db:
        all_notes = await get_all_pattern_notes(db, user_id)

    if pattern:
        return {pattern: all_notes.get(pattern, {"notes": "", "memory_techniques": ""})}
    return all_notes


@mcp.tool()
async def get_all_users() -> list[dict]:
    """
    List all registered users with their ID, username, email, and role.
    Useful for finding a user_id before querying their data.
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from sqlalchemy.future import select

    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        return [
            {
                "id": u.id,
                "username": u.username,
                "email": u.email,
                "role": u.role,
            }
            for u in users
        ]


@mcp.tool()
async def run_study_coach(user_id: int) -> str:
    """
    Run the agentic study coach for a user and return their personalized
    study plan for today. The agent queries due questions, weak areas, and
    stats before producing a recommendation.

    Args:
        user_id: The user's numeric ID
    """
    from backend.db.session import AsyncSessionLocal
    from backend.db.models import User
    from sqlalchemy.future import select
    from backend.services.agent import agentic_study_coach

    async with AsyncSessionLocal() as db:
        user = (await db.execute(
            select(User).where(User.id == user_id)
        )).scalar_one_or_none()

    if not user:
        return f"User {user_id} not found."

    plan = await agentic_study_coach(user_id, user.username)
    return plan or "No study plan generated (check ANTHROPIC_API_KEY)."


# ── Entry point ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run()
