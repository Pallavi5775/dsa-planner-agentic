"""
Admin Upload Agent.

When an admin uploads a markdown file, this agent:
1. Checks existing questions to skip duplicates
2. Reads existing patterns to stay consistent
3. For each new question: determines pattern, difficulty, and writes a hint
4. Adds questions to the DB
5. Returns a rich import report

This replaces the dumb parse-and-insert with an intelligent import
that enriches every question with metadata.
"""

import json
import logging
import os

from openai import AsyncOpenAI
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

MODEL = "gpt-4o-mini"
MAX_ITERATIONS = 20  # More iterations needed — one per question


def _client() -> AsyncOpenAI:
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))


# ── Tool implementations ────────────────────────────────────────────────────────

async def _tool_get_existing_titles(db: AsyncSession) -> list[str]:
    from backend.db.models import Question
    from sqlalchemy.future import select
    rows = (await db.execute(select(Question.title))).scalars().all()
    return list(rows)


async def _tool_get_existing_patterns(db: AsyncSession) -> list[str]:
    from backend.db.models import Question
    from sqlalchemy.future import select
    rows = (await db.execute(select(Question.pattern).distinct())).scalars().all()
    return sorted(set(r for r in rows if r))


async def _tool_add_question(
    db: AsyncSession,
    title: str,
    pattern: str,
    difficulty: str,
    category: str,
    hint: str,
) -> dict:
    from backend.db.models import Question
    from sqlalchemy.future import select

    existing = (await db.execute(
        select(Question).where(Question.title == title)
    )).scalar_one_or_none()

    if existing:
        return {"status": "duplicate", "title": title}

    valid_difficulties = {"Easy", "Medium", "Hard"}
    if difficulty not in valid_difficulties:
        difficulty = "Medium"

    q = Question(
        title=title,
        pattern=pattern,
        category=category or "Mixed",
        difficulty=difficulty,
        hint=hint or None,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return {"status": "added", "title": title, "id": q.id}


# ── Tool schemas ────────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_existing_titles",
            "description": "Get all question titles already in the database so you can skip duplicates.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_existing_patterns",
            "description": "Get all DSA patterns currently in the database so you stay consistent with naming.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_question",
            "description": (
                "Add a single DSA question to the database. "
                "Use your DSA knowledge to assign pattern, difficulty, and a helpful hint. "
                "Returns 'added' or 'duplicate'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title":      {"type": "string", "description": "Exact question title"},
                    "pattern":    {"type": "string", "description": "DSA pattern (e.g. 'Two Pointers', 'Sliding Window', 'Binary Search')"},
                    "difficulty": {"type": "string", "enum": ["Easy", "Medium", "Hard"]},
                    "category":   {"type": "string", "description": "Category (e.g. 'Arrays', 'Strings', 'Trees'). Default: Mixed"},
                    "hint":       {"type": "string", "description": "One sentence hint — what approach or data structure to think about"},
                },
                "required": ["title", "pattern", "difficulty", "category", "hint"],
            },
        },
    },
]


# ── Agent loop ──────────────────────────────────────────────────────────────────

async def run_admin_upload_agent(content: str, db: AsyncSession) -> dict:
    """
    Run the admin upload agent on raw markdown content.

    Returns a report dict:
    {
        "added": [...],
        "skipped_duplicates": [...],
        "total_added": N,
        "total_skipped": N,
        "summary": "..."
    }
    """
    client = _client()

    async def execute(name: str, args: dict) -> dict:
        try:
            if name == "get_existing_titles":
                return {"titles": await _tool_get_existing_titles(db)}
            if name == "get_existing_patterns":
                return {"patterns": await _tool_get_existing_patterns(db)}
            if name == "add_question":
                return await _tool_add_question(
                    db,
                    title=args["title"],
                    pattern=args["pattern"],
                    difficulty=args["difficulty"],
                    category=args.get("category", "Mixed"),
                    hint=args.get("hint", ""),
                )
            return {"error": f"Unknown tool: {name}"}
        except Exception as e:
            log.warning("Admin agent tool %s failed: %s", name, e)
            # Return structured error so it appears in the trace
            return {
                "error": str(e),
                "error_type": type(e).__name__,
                "tool": name,
                "hint": "Check if the database migration has been run: alembic upgrade head",
            }

    system = (
        "You are an expert DSA curriculum curator importing questions into a learning platform.\n\n"
        "Your process:\n"
        "1. Call get_existing_titles() to know what's already in the DB\n"
        "2. Call get_existing_patterns() to see existing pattern names — reuse them exactly when they match\n"
        "3. Parse every DSA question from the markdown the user provided\n"
        "4. For each question NOT already in the DB: call add_question() with:\n"
        "   - The exact title as written\n"
        "   - The correct DSA pattern using your knowledge\n"
        "   - Appropriate difficulty (Easy/Medium/Hard)\n"
        "   - The category (Arrays, Strings, Trees, Graphs, etc.)\n"
        "   - A one-sentence hint that nudges without giving away the solution\n"
        "5. After processing all questions, write a brief summary of what was imported\n\n"
        "Be thorough — process every single question in the file. "
        "Prefer reusing existing pattern names for consistency."
    )

    from backend.services.agent_logger import (
        log_agent_start, log_agent_end,
        log_tool_call as _log_call, log_tool_result as _log_result,
    )
    log_agent_start("admin-upload-agent", "Import DSA questions from uploaded markdown file")

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": f"Import all DSA questions from this markdown file:\n\n{content}"},
    ]

    added   = []
    skipped = []
    trace   = []   # full record of every tool call the agent made
    step    = 0

    for _ in range(MAX_ITERATIONS):
        response = await client.chat.completions.create(
            model=MODEL,
            max_tokens=2000,
            tools=_TOOLS,
            tool_choice="auto",
            messages=messages,
        )

        choice  = response.choices[0]
        message = choice.message

        if choice.finish_reason == "stop":
            summary = message.content or "Import complete."
            break

        if choice.finish_reason == "tool_calls" and message.tool_calls:
            messages.append(message)
            for tc in message.tool_calls:
                step += 1
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                log.info("[admin-agent] → %s(%s)", tc.function.name,
                         ", ".join(f"{k}={repr(v)[:40]}" for k, v in args.items()))
                _log_call("admin-upload-agent", tc.function.name, args, step=step)
                result = await execute(tc.function.name, args)
                log.info("[admin-agent] ← %s", str(result)[:100])
                _log_result("admin-upload-agent", tc.function.name, result, step=step)

                # Build a human-readable summary for the trace
                tool_name = tc.function.name
                has_error = "error" in result

                if has_error:
                    result_summary = f"❌ ERROR: {result['error']}"
                    if result.get("hint"):
                        result_summary += f" — {result['hint']}"
                elif tool_name == "get_existing_titles":
                    count = len(result.get("titles", []))
                    result_summary = f"Found {count} existing questions in the database"
                elif tool_name == "get_existing_patterns":
                    patterns = result.get("patterns", [])
                    result_summary = f"Found {len(patterns)} patterns: {', '.join(patterns[:6])}{'…' if len(patterns) > 6 else ''}"
                elif tool_name == "add_question":
                    status = result.get("status", "unknown")
                    if status == "added":
                        result_summary = f"✅ Added — pattern: {args.get('pattern')}, difficulty: {args.get('difficulty')}"
                    elif status == "duplicate":
                        result_summary = "⏭ Skipped — already exists in database"
                    else:
                        result_summary = f"⚠ {result.get('error', status)}"
                else:
                    result_summary = json.dumps(result, default=str)[:120]

                trace.append({
                    "step":           step,
                    "tool":           tool_name,
                    "input":          args,
                    "result_summary": result_summary,
                    "status":         result.get("status"),
                    "is_error":       has_error,
                    "error_detail":   result.get("error") if has_error else None,
                })

                # Track added/skipped
                if tool_name == "add_question":
                    if result.get("status") == "added":
                        added.append({
                            "title":      args.get("title"),
                            "pattern":    args.get("pattern"),
                            "difficulty": args.get("difficulty"),
                            "hint":       args.get("hint"),
                        })
                    elif result.get("status") == "duplicate":
                        skipped.append(args.get("title"))

                messages.append({
                    "role":         "tool",
                    "tool_call_id": tc.id,
                    "content":      json.dumps(result, default=str),
                })
        else:
            summary = message.content or "Import complete."
            break
    else:
        summary = f"Import complete. Processed {len(added) + len(skipped)} questions."

    log_agent_end("admin-upload-agent", summary)

    return {
        "added":              added,
        "skipped_duplicates": skipped,
        "total_added":        len(added),
        "total_skipped":      len(skipped),
        "summary":            summary,
        "trace":              trace,
        "total_tool_calls":   step,
    }
