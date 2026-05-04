# -*- coding: utf-8 -*-
import os
import re
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException

from backend.db.models import Question, PracticeLog, UserQuestionProgress, User
from backend.core.utils import (
    get_spaced_repetition_values,
    calculate_accuracy,
    parse_questions_from_md,
    compute_next_revision,
    snap_to_practice_day,
    first_revision_date,
)


def _defaults() -> dict:
    return {
        "coverage_status": "Not Covered",
        "revision_status": "Pending",
        "ease_factor": 2.5,
        "interval_days": 0,
        "next_revision": None,
        "accuracy": None,
        "suggestions": None,
        "notes": None,
        "my_gap_analysis": None,
    }


def _question_to_dict(q: Question, progress: UserQuestionProgress | None, user_logs: list) -> dict:
    p = progress
    d = _defaults()
    if p:
        d.update({
            "coverage_status": p.coverage_status,
            "revision_status": p.revision_status,
            "ease_factor": p.ease_factor,
            "interval_days": p.interval_days,
            "next_revision": p.next_revision,
            "accuracy": p.accuracy,
            "suggestions": p.suggestions,
            "notes": p.notes,
            "my_gap_analysis": p.my_gap_analysis,
        })
    return {
        "id": q.id,
        "title": q.title,
        "pattern": q.pattern,
        "category": q.category,
        "difficulty": q.difficulty,
        "hint": q.hint,
        **d,
        "total_time_spent": sum(log.time_taken for log in user_logs) // 60,
        "logs": [
            {
                "id": log.id,
                "question_id": log.question_id,
                "date": log.date,
                "logic": log.logic,
                "code": log.code,
                "time_taken": log.time_taken,
                "correct": log.correct,
                "hint_used": log.hint_used,
            }
            for log in user_logs
        ],
    }


async def _get_or_create_progress(
    db: AsyncSession, question_id: int, user_id: int
) -> UserQuestionProgress:
    result = await db.execute(
        select(UserQuestionProgress).where(
            UserQuestionProgress.question_id == question_id,
            UserQuestionProgress.user_id == user_id,
        )
    )
    p = result.scalar_one_or_none()
    if p is None:
        p = UserQuestionProgress(question_id=question_id, user_id=user_id)
        db.add(p)
        await db.flush()
    return p


async def _get_user_logs(db: AsyncSession, question_id: int, user_id: int) -> list:
    result = await db.execute(
        select(PracticeLog).where(
            PracticeLog.question_id == question_id,
            PracticeLog.user_id == user_id,
        )
    )
    return result.scalars().all()


async def get_activity(db: AsyncSession, user_id: int, tz: str = "UTC") -> dict:
    try:
        _tz = ZoneInfo(tz)
    except Exception:
        _tz = ZoneInfo("UTC")

    logs_result = await db.execute(
        select(PracticeLog, Question)
        .join(Question, PracticeLog.question_id == Question.id)
        .where(PracticeLog.user_id == user_id)
    )
    rows = logs_result.all()

    now_local = datetime.now(_tz)
    today = now_local.strftime("%Y-%m-%d")
    today_dt = now_local.date()
    week_start = (today_dt - timedelta(days=today_dt.weekday())).strftime("%Y-%m-%d")

    all_logs = []
    sessions_by_date = {}
    pattern_counts = {}
    daily_correct = {}
    daily_wrong = {}
    time_by_pattern = {}

    for log, q in rows:
        entry = {
            "date": log.date or today,
            "question_title": q.title,
            "pattern": q.pattern or "",
            "time_taken": log.time_taken or 0,
            "correct": log.correct,
        }
        all_logs.append(entry)
        d = log.date or today
        sessions_by_date[d] = sessions_by_date.get(d, 0) + 1
        if log.correct:
            daily_correct[d] = daily_correct.get(d, 0) + 1
        else:
            daily_wrong[d] = daily_wrong.get(d, 0) + 1
        if q.pattern:
            pattern_counts[q.pattern] = pattern_counts.get(q.pattern, 0) + 1
            time_by_pattern[q.pattern] = time_by_pattern.get(q.pattern, 0) + (log.time_taken or 0)

    all_logs.sort(key=lambda x: x["date"], reverse=True)

    today_logs = [l for l in all_logs if l["date"] == today]
    weekly_logs = [l for l in all_logs if l["date"] >= week_start]

    streak, check = 0, today_dt
    from datetime import timedelta as td
    while sessions_by_date.get(check.strftime("%Y-%m-%d"), 0) > 0:
        streak += 1
        check -= td(days=1)

    return {
        "total_sessions": len(all_logs),
        "total_time_minutes": sum(l["time_taken"] for l in all_logs) // 60,
        "today_sessions": len(today_logs),
        "today_time_minutes": sum(l["time_taken"] for l in today_logs) // 60,
        "weekly_sessions": len(weekly_logs),
        "streak_days": streak,
        "sessions_by_date": sessions_by_date,
        "recent_sessions": all_logs[:50],
        "pattern_counts": dict(
            sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
        ),
        "daily_correct": daily_correct,
        "daily_wrong": daily_wrong,
        "time_by_pattern": dict(
            sorted(time_by_pattern.items(), key=lambda x: x[1], reverse=True)
        ),
    }


async def get_questions(db: AsyncSession, user_id: int):
    questions = (await db.execute(select(Question))).scalars().all()

    progress_map = {
        p.question_id: p
        for p in (await db.execute(
            select(UserQuestionProgress).where(UserQuestionProgress.user_id == user_id)
        )).scalars().all()
    }

    logs_result = await db.execute(
        select(PracticeLog).where(PracticeLog.user_id == user_id)
    )
    logs_by_qid: dict[int, list] = {}
    for log in logs_result.scalars().all():
        logs_by_qid.setdefault(log.question_id, []).append(log)

    out = []
    for q in questions:
        progress = progress_map.get(q.id)
        user_logs = logs_by_qid.get(q.id, [])
        d = _question_to_dict(q, progress, user_logs)
        # Use AI-validated accuracy from progress when available; fall back to log-based
        if progress is not None and progress.accuracy is not None:
            d["accuracy"] = progress.accuracy
        else:
            d["accuracy"] = calculate_accuracy(user_logs)
        ease_f = progress.ease_factor if progress else 2.5
        interval = progress.interval_days if progress else 0
        d["interval_days"], d["ease_factor"] = get_spaced_repetition_values(user_logs, ease_f, interval)
        out.append(d)
    return out


async def create_question(db: AsyncSession, data, user_id: int):
    q = Question(
        title=data.title,
        pattern=data.pattern,
        category=data.category,
        difficulty=data.difficulty,
        hint=data.hint if hasattr(data, "hint") else None,
    )
    db.add(q)
    await db.commit()
    await db.refresh(q)
    return _question_to_dict(q, None, [])


async def update_question(db: AsyncSession, qid: int, data, user_id: int):
    result = await db.execute(select(Question).where(Question.id == qid))
    q = result.scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    q.title = data.title
    q.pattern = data.pattern
    q.category = data.category
    q.difficulty = data.difficulty
    if hasattr(data, "hint"):
        q.hint = data.hint
    await db.commit()
    await db.refresh(q)
    progress = (await db.execute(
        select(UserQuestionProgress).where(
            UserQuestionProgress.question_id == qid,
            UserQuestionProgress.user_id == user_id,
        )
    )).scalar_one_or_none()
    user_logs = await _get_user_logs(db, qid, user_id)
    return _question_to_dict(q, progress, user_logs)


async def update_question_status(
    db: AsyncSession, qid: int, category: str, coverage_status: str,
    revision_status: str, user_id: int,
):
    result = await db.execute(select(Question).where(Question.id == qid))
    q = result.scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")

    p = await _get_or_create_progress(db, qid, user_id)
    p.coverage_status = coverage_status
    p.revision_status = revision_status
    await db.commit()
    await db.refresh(p)
    user_logs = await _get_user_logs(db, qid, user_id)
    return _question_to_dict(q, p, user_logs)


async def add_log(db: AsyncSession, qid: int, log_data: dict, user_id: int):
    result = await db.execute(select(Question).where(Question.id == qid))
    q = result.scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")

    log = PracticeLog(
        question_id=qid,
        user_id=user_id,
        date=log_data.get("date") or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        logic=log_data.get("logic", ""),
        code=log_data.get("code", ""),
        time_taken=min(log_data.get("time_taken", 0), 3600),
        correct=log_data.get("correct", True),
        hint_used=log_data.get("hint_used", False),
    )
    db.add(log)
    await db.commit()

    progress = await _get_or_create_progress(db, qid, user_id)
    user_logs = await _get_user_logs(db, qid, user_id)

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    practice_days = user.practice_days if user else ""

    new_interval, new_ease = get_spaced_repetition_values(
        user_logs, progress.ease_factor, progress.interval_days
    )
    progress.interval_days = new_interval
    progress.ease_factor = new_ease

    if len(user_logs) == 1:
        progress.next_revision = first_revision_date(log.date, practice_days)
    else:
        progress.next_revision = compute_next_revision(log.date, new_interval, practice_days)

    # Update coverage and set a preliminary revision_status (AI validation will override)
    progress.coverage_status = "Covered"
    if progress.revision_status == "Pending":
        acc = calculate_accuracy(user_logs)
        progress.revision_status = "Mastered" if acc >= 90 else "Needs Work"

    await db.commit()

    return _question_to_dict(q, progress, user_logs)


async def update_notes(db: AsyncSession, qid: int, notes: str, my_gap_analysis: str, user_id: int):
    result = await db.execute(select(Question).where(Question.id == qid))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Question not found")
    p = await _get_or_create_progress(db, qid, user_id)
    p.notes = notes
    p.my_gap_analysis = my_gap_analysis
    await db.commit()
    return {"status": "ok"}


async def get_last_log(db: AsyncSession, qid: int, user_id: int) -> dict | None:
    """Return the most recent PracticeLog for a question + the progress notes/gap."""
    logs = await _get_user_logs(db, qid, user_id)
    if not logs:
        return None
    latest = max(logs, key=lambda l: (l.date or ""), default=None)
    if not latest:
        return None

    result = await db.execute(select(Question).where(Question.id == qid))
    q = result.scalar_one_or_none()

    progress_res = await db.execute(
        select(UserQuestionProgress).where(
            UserQuestionProgress.question_id == qid,
            UserQuestionProgress.user_id == user_id,
        )
    )
    p = progress_res.scalar_one_or_none()

    return {
        "log_id":        latest.id,
        "date":          latest.date or "",
        "logic":         latest.logic or "",
        "code":          latest.code or "",
        "time_taken":    latest.time_taken or 0,
        "correct":       latest.correct,
        "notes":         p.notes if p else "",
        "my_gap_analysis": p.my_gap_analysis if p else "",
        "question_title":  q.title if q else "",
        "pattern":         q.pattern if q else "",
        "difficulty":      q.difficulty if q else "",
    }


async def update_last_log(db: AsyncSession, qid: int, user_id: int,
                          logic: str, code: str,
                          notes: str, my_gap_analysis: str) -> dict:
    """Update logic+code on the most recent PracticeLog and notes/gap on progress."""
    logs = await _get_user_logs(db, qid, user_id)
    if not logs:
        raise HTTPException(status_code=404, detail="No practice log found for this question")

    latest = max(logs, key=lambda l: (l.date or ""))
    latest.logic = logic
    latest.code = code

    p = await _get_or_create_progress(db, qid, user_id)
    p.notes = notes
    p.my_gap_analysis = my_gap_analysis

    await db.commit()
    return {"status": "ok", "log_id": latest.id}


async def validate_question(db: AsyncSession, qid: int, user_id: int):
    result = await db.execute(select(Question).where(Question.id == qid))
    q = result.scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")

    p = await _get_or_create_progress(db, qid, user_id)
    user_logs = await _get_user_logs(db, qid, user_id)
    question_dict = _question_to_dict(q, p, user_logs)

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    latest_log = user_logs[-1] if user_logs else None
    hint_used_this_session = latest_log.hint_used if latest_log else False
    hint_text = q.hint or "(none)"

    prompt = f"""
You are an expert DSA Tutor and Spaced Repetition System (SRS).
Your task is to analyze a student's session and update the question metadata.

### INPUT DATA (Current Question Object):
{json.dumps(question_dict, ensure_ascii=False)}

### STUDENT'S SELF-REFLECTION (use these to calibrate accuracy):
- **Notes (key insights the student wrote):** {p.notes or "(none)"}
- **My Gap Analysis (student's own weakness assessment):** {p.my_gap_analysis or "(none)"}
- **Hint used this session:** {"YES — the student viewed the hint before/during solving. Apply up to -15 points to accuracy to reflect reduced independence. Hint was: " + hint_text if hint_used_this_session else "No"}

### TASK 1: VALIDATION
- If logic AND code AND notes AND my_gap_analysis are all empty or gibberish, mark `correct = false`.
- If the student attempts a solution but uses the wrong strategy, mark `correct = false` but acknowledge the valid attempt.

### TASK 2: TECHNICAL ANALYSIS
- Strategy Matching: Compare the student's logic and code against the optimal strategy for the {q.pattern} pattern and problem {q.title}.
- Self-Awareness Check: Does the student's `my_gap_analysis` correctly identify their own weakness? If yes, add up to +10 points to accuracy (self-awareness bonus).
- Notes Quality: Do the `notes` capture the core insight of the pattern? If yes, add up to +5 points.
- The "Why" Analysis:
      - If Correct: Explain why this approach leads to the correct solution and what makes it optimal.
      - If Incorrect: Explain the logical flaw precisely — what assumption broke and why.
- Complexity Check: Verify if the time complexity matches optimal O(n log n) or O(n).

### TASK 3: ASSESSMENT ONLY (backend handles all SRS scheduling)
1. accuracy: 0-100. Base score from code/logic quality. Add bonuses. Cap at 100.
2. correct: true if the approach and code are logically valid, false otherwise.
3. revision_status: "Mastered" if accuracy > 90%, "Needs Work" if accuracy < 60%, "Pending" if gibberish.
4. suggestions: A detailed 4-6 sentence analysis covering:
   (a) What the student did well — cite specific parts of their logic or code.
   (b) The key issue or gap found — be precise, not vague.
   (c) WHY the accuracy score was assigned — e.g. "The score of 72% reflects a valid two-pointer approach but incorrect handling of duplicates and O(n²) fallback in the inner loop."
   (d) Whether the student's own gap analysis was accurate or missed the real issue.
   (e) One concrete next-practice focus to close the identified gap.
5. gap_analysis (HTML string): Structured HTML with four labeled sections separated by line breaks:
   "<b>Score Reasoning:</b> [explain exactly why this % was given — cite specific strengths that boosted the score and specific weaknesses that reduced it]<br><br>
    <b>Observations:</b> [what the student's logic, code, and self-analysis reveal about their current understanding level]<br><br>
    <b>Pattern Gaps:</b> [what specific pattern knowledge, technique, or edge case handling is missing or shaky]<br><br>
    <b>Next Focus:</b> [one concrete, actionable improvement to target in the very next practice session]"

DO NOT calculate ease_factor, interval_days, or next_revision. The backend computes these.

### JSON RESPONSE REQUIREMENTS:
Return ONLY a valid JSON object. No markdown. No preamble.
{{
    "correct": boolean,
    "gap_analysis": "HTML string with Score Reasoning, Observations, Pattern Gaps, Next Focus sections",
    "gap_explanation": "Plain text version of the gap analysis",
    "correction_suggestion": "The optimal implementation hint...",
    "updated_fields": {{
        "accuracy": float,
        "revision_status": "string",
        "suggestions": "4-6 sentence detailed analysis with score reasoning"
    }}
}}
"""

    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a strict DSA tutor. If input is gibberish, mark it incorrect. Output strictly JSON."},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=1800,
            temperature=0,
        )

        raw = response.choices[0].message.content.strip()
        json_match = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(json_match.group(0)) if json_match else None

        if data and "updated_fields" in data:
            uf = data["updated_fields"]
            correct = data.get("correct", False)

            p.accuracy = uf.get("accuracy", p.accuracy)
            p.suggestions = uf.get("suggestions", p.suggestions)
            p.coverage_status = "Covered"
            p.revision_status = uf.get("revision_status", "Mastered" if correct else "Needs Work")

            # SRS: backend owns interval and ease calculation
            new_interval, new_ease = get_spaced_repetition_values(
                user_logs, p.ease_factor, p.interval_days, correct=correct
            )
            p.interval_days = new_interval
            p.ease_factor = new_ease

            # Schedule-aware next revision date
            user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
            practice_days = user.practice_days if user else ""
            base = user_logs[-1].date if user_logs else today
            if len(user_logs) <= 1:
                p.next_revision = first_revision_date(base, practice_days)
            else:
                from datetime import timedelta
                ai_date = (datetime.strptime(base, "%Y-%m-%d") + timedelta(days=new_interval)).strftime("%Y-%m-%d")
                p.next_revision = snap_to_practice_day(ai_date, practice_days)

            await db.commit()

        return data

    except Exception as e:
        return {"correct": False, "gap_analysis": f"OpenAI validation failed: {e}"}


async def recalculate_next_revisions(db: AsyncSession, user_id: int, practice_days: str) -> int:
    progress_rows = (await db.execute(
        select(UserQuestionProgress).where(UserQuestionProgress.user_id == user_id)
    )).scalars().all()

    all_logs = (await db.execute(
        select(PracticeLog).where(PracticeLog.user_id == user_id)
    )).scalars().all()

    last_date_by_qid: dict[int, str] = {}
    log_count_by_qid: dict[int, int] = {}
    for log in all_logs:
        log_count_by_qid[log.question_id] = log_count_by_qid.get(log.question_id, 0) + 1
        existing = last_date_by_qid.get(log.question_id)
        if existing is None or log.date > existing:
            last_date_by_qid[log.question_id] = log.date

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    updated = 0
    for p in progress_rows:
        if not p.interval_days:
            continue
        base = last_date_by_qid.get(p.question_id, today)
        count = log_count_by_qid.get(p.question_id, 0)
        if count <= 1:
            p.next_revision = first_revision_date(base, practice_days)
        else:
            p.next_revision = compute_next_revision(base, p.interval_days, practice_days)
        updated += 1

    await db.commit()
    return updated


async def sync_questions_from_file(db: AsyncSession) -> int:
    dsa_file = "DSA_Must_Solve_Problems.md"
    if not os.path.exists(dsa_file):
        return 0

    with open(dsa_file, "r", encoding="utf-8") as f:
        content = f.read()

    return await _upsert_questions(db, parse_questions_from_md(content))


async def add_questions_from_md(db: AsyncSession, content: str):
    questions = parse_questions_from_md(content)
    added = await _upsert_questions(db, questions)
    total = (await db.execute(select(Question))).scalars().__class__  # just count
    total_count = len((await db.execute(select(Question))).scalars().all())
    return added, total_count


async def _upsert_questions(db: AsyncSession, questions: list) -> int:
    existing_titles = {
        q.title for q in (await db.execute(select(Question))).scalars().all()
    }
    added = 0
    seen_in_batch: set[str] = set()
    for q_data in questions:
        title = q_data["title"]
        if title not in existing_titles and title not in seen_in_batch:
            db.add(Question(
                title=title,
                pattern=q_data["pattern"],
                category=q_data.get("category", "Mixed"),
                difficulty=q_data.get("difficulty", "Medium"),
            ))
            seen_in_batch.add(title)
            added += 1
    if added:
        await db.commit()
    return added


async def hint_chat(db: AsyncSession, qid: int, message: str, context: dict) -> dict:
    result = await db.execute(select(Question).where(Question.id == qid))
    q = result.scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")

    user_logic = (context.get("logic") or "").strip()
    user_code  = (context.get("code")  or "").strip()

    system_prompt = (
        f"You are a Socratic DSA tutor helping a student practice '{q.title}' "
        f"(Pattern: {q.pattern}, Difficulty: {q.difficulty or 'Medium'}).\n\n"
        f"Student's current approach:\n{user_logic or '(not written yet)'}\n\n"
        f"Student's current code:\n{user_code or '(not written yet)'}\n\n"
        "Rules you MUST follow:\n"
        "- Reply in AT MOST 2 short sentences.\n"
        "- NEVER reveal the full algorithm or complete solution.\n"
        "- Guide with a probing question or a tiny directional nudge.\n"
        "- If the student is on the right track, confirm briefly and push one step further.\n"
        "- Be warm and encouraging, but stay concise."
    )

    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": message},
            ],
            max_tokens=120,
            temperature=0.7,
        )
        reply = response.choices[0].message.content.strip()
    except Exception as e:
        reply = f"(AI unavailable: {e})"

    return {"reply": reply}
