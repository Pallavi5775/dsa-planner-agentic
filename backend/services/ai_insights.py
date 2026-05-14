import os
from datetime import datetime, timezone

from openai import AsyncOpenAI


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

MODEL = "gpt-4o-mini"


async def generate_session_insight(session: dict) -> str:
    """
    Given a single practice session dict, return a markdown insight string
    to be committed to the user's GitHub repo.
    """
    minutes = session.get("time_taken_seconds", 0) // 60
    seconds = session.get("time_taken_seconds", 0) % 60
    time_str = f"{minutes}m {seconds}s" if minutes else f"{seconds}s"

    prompt = f"""You are an encouraging DSA coach reviewing a student's practice session.
Write a short, motivating markdown insight (≤ 250 words). Be specific, not generic.

Session:
- Problem : {session.get('question')}
- Pattern : {session.get('pattern', 'Unknown')}
- Difficulty: {session.get('difficulty', 'Unknown')}
- Date    : {session.get('date')}
- Correct : {'Yes' if session.get('correct') else 'No'}
- Time    : {time_str}
- Logic   : {session.get('logic') or '(not provided)'}
- Code    : {session.get('code') or '(not provided)'}

Format exactly like this (no extra text outside):
# {session.get('question')} — {session.get('date')}

## Quick Stats
- ✅ Correct: {'Yes' if session.get('correct') else 'No'}
- ⏱️ Time: {time_str}
- 🧠 Pattern: {session.get('pattern', 'Unknown')}

## What went well
<1-2 sentences>

## To improve
<1-2 sentences>

## Key takeaway
<One sentence the student should remember next time>
"""

    client = _client()
    resp = await client.chat.completions.create(
        model=MODEL,
        max_tokens=600,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


async def generate_weekly_summary(sessions: list[dict], username: str) -> str:
    """
    Given all sessions from the past week, return a markdown weekly summary.
    """
    if not sessions:
        return ""

    # Filter to this week
    today = datetime.now(timezone.utc)
    week_num = today.isocalendar()[1]
    year = today.year
    week_label = f"{year}-W{week_num:02d}"

    # Build a compact summary for the prompt
    lines = []
    for s in sessions:
        lines.append(
            f"- {s.get('date')} | {s.get('question')} | {s.get('pattern','?')} | "
            f"{'✅' if s.get('correct') else '❌'} | {s.get('time_taken_seconds',0)//60}min"
        )
    sessions_text = "\n".join(lines)

    total_min = sum(s.get("time_taken_seconds", 0) for s in sessions) // 60
    correct_count = sum(1 for s in sessions if s.get("correct"))

    prompt = f"""You are a DSA coach writing a weekly review for {username}.
Write an encouraging, data-driven markdown summary (≤ 400 words).

Week: {week_label}
Sessions this week:
{sessions_text}

Stats: {len(sessions)} sessions, {total_min} total minutes, {correct_count}/{len(sessions)} correct

Format:
# Weekly Summary — {week_label}

## Stats
- Sessions: {len(sessions)}
- Total time: {total_min} min
- Accuracy: {round(correct_count/len(sessions)*100)}%

## Strongest patterns this week
<bullet points>

## Patterns needing attention
<bullet points>

## Recommendations for next week
<3 actionable bullet points>

## Motivational note
<One short, personal closing thought>
"""

    client = _client()
    resp = await client.chat.completions.create(
        model=MODEL,
        max_tokens=800,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content or ""


def has_api_key() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))
