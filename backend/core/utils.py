import re
from datetime import datetime, timedelta


def first_revision_date(base_date: str, practice_days: str) -> str:
    """First review: 7 calendar days after practice, snapped to next valid practice day."""
    dt = datetime.strptime(base_date, "%Y-%m-%d") + timedelta(days=7)
    return snap_to_practice_day(dt.strftime("%Y-%m-%d"), practice_days)


def snap_to_practice_day(ai_date: str, practice_days: str) -> str:
    """
    If ai_date falls on a practice day, return it unchanged.
    Otherwise advance forward until the next valid practice day.
    If practice_days is empty (daily), return ai_date as-is.
    """
    if not practice_days:
        return ai_date
    days = set(int(d) for d in practice_days.split(",") if d.strip())
    dt = datetime.strptime(ai_date, "%Y-%m-%d")
    while dt.weekday() not in days:
        dt += timedelta(days=1)
    return dt.strftime("%Y-%m-%d")


def compute_next_revision(base_date: str, interval: int, practice_days: str) -> str:
    """
    Return the date of the interval-th next practice day after base_date.
    practice_days: comma-separated weekday numbers (0=Mon … 6=Sun), empty = daily.
    """
    base = datetime.strptime(base_date, "%Y-%m-%d")
    if not practice_days:
        return (base + timedelta(days=interval)).strftime("%Y-%m-%d")

    days = set(int(d) for d in practice_days.split(",") if d.strip())
    count = 0
    current = base + timedelta(days=1)
    while True:
        if current.weekday() in days:
            count += 1
            if count == interval:
                break
        current += timedelta(days=1)
    return current.strftime("%Y-%m-%d")


def get_spaced_repetition_values(logs, current_ease, current_interval, correct=None):
    if not logs:
        return 1, 2.5

    last = logs[-1]
    time_taken = last.time_taken if hasattr(last, "time_taken") else last.get("time_taken", 0)
    if correct is None:
        correct = last.correct if hasattr(last, "correct") else last.get("correct", True)

    if time_taken <= 7:
        difficulty_score = 1
    elif time_taken >= 15:
        difficulty_score = 5
    else:
        difficulty_score = 3

    quality = 6 - difficulty_score if correct else 0

    new_ease = current_ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_ease = max(1.3, new_ease)

    if not correct:
        new_interval = 1
    elif current_interval == 0:
        new_interval = 1
    elif current_interval == 1:
        new_interval = 3
    else:
        new_interval = round(current_interval * new_ease)

    return new_interval, new_ease


def calculate_accuracy(logs):
    total = len(logs)
    if total == 0:
        return 0.0
    correct = sum(
        1 for log in logs
        if (log.correct if hasattr(log, "correct") else log.get("correct", False))
    )
    return round(correct / total * 100, 2)


def calculate_difficulty_from_time(time_taken: int) -> str:
    if time_taken <= 7:
        return "Easy"
    elif time_taken >= 15:
        return "Hard"
    return "Medium"


def format_dsa_feedback(data: dict) -> str:
    gap_analysis = data.get("gap_analysis", "")
    correction_suggestion = data.get("correction_suggestion", "")
    uf = data.get("updated_fields", {})
    return f"""
<div style="margin-bottom:1em;">
    <h4>Gap Analysis</h4>
    {gap_analysis}
</div>
<div style="margin-bottom:1em;">
    <h4>Correction Suggestion</h4>
    <div style="background:#f8f8fa; border-left:4px solid #eebbc3; padding:8px; border-radius:4px;">{correction_suggestion}</div>
</div>
<div style="margin-bottom:1em;">
    <h4>Updated Fields</h4>
    <ul style="margin:0 0 0 1em;">
        <li><b>Accuracy:</b> {uf.get('accuracy', '')}%</li>
        <li><b>Revision Status:</b> {uf.get('revision_status', '')}</li>
        <li><b>Next Revision:</b> {uf.get('next_revision', '')}</li>
        <li><b>Ease Factor:</b> {uf.get('ease_factor', '')}</li>
        <li><b>Interval Days:</b> {uf.get('interval_days', '')}</li>
        <li><b>Suggestions:</b> {uf.get('suggestions', '')}</li>
    </ul>
</div>
"""


def parse_questions_from_md(content: str) -> list:
    pattern_blocks = re.split(r"## ", content)[1:]
    questions = []
    for block in pattern_blocks:
        lines = block.splitlines()
        if not lines:
            continue
        pattern = lines[0].split("(")[0].strip()
        for line in lines[1:]:
            m = re.match(r"\d+\. (.+)", line.strip())
            if m:
                questions.append({
                    "title": m.group(1).strip(),
                    "pattern": pattern,
                    "category": "Mixed",
                    "coverage_status": "Not Covered",
                    "revision_status": "Pending",
                    "ease_factor": 2.5,
                    "interval_days": 0,
                    "accuracy": None,
                    "suggestions": None,
                    "difficulty": "Medium",
                    "next_revision": None,
                })
    return questions
