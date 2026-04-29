import logging
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

log = logging.getLogger(__name__)

from backend.db.session import get_db
from backend.db.models import User
from backend.crud import question as crud
from backend.schemas.question import QuestionCreate
from backend.core.security import get_current_user_id, require_admin

router = APIRouter()


async def _validate_then_push(user_id: int, qid: int, session_data: dict) -> None:
    """Background task: AI-validate the session, then push to GitHub with gap_analysis included."""
    q = session_data.get("question", "?")
    log.info("[session] starting validate+push for user=%s qid=%s", user_id, qid)
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.db.models import User as UserModel
        from backend.services.github_storage import GitHubStorageService
        from backend.services.ai_insights import generate_session_insight, has_api_key

        # Step 1 — AI validate: saves accuracy/suggestions/revision_status to DB
        gap_analysis = ""
        try:
            async with AsyncSessionLocal() as db:
                result = await crud.validate_question(db, qid, user_id)
            gap_analysis = result.get("gap_analysis", "") if result else ""
            log.info("[session] validate done for qid=%s correct=%s", qid, result.get("correct") if result else "no-result")
        except Exception as ve:
            log.error("[session] validate failed for qid=%s: %s", qid, ve, exc_info=True)

        # Step 2 — push to GitHub (skip if no GitHub token)
        async with AsyncSessionLocal() as db:
            user = await db.get(UserModel, user_id)
        if not user or not user.github_access_token or not user.github_username:
            log.info("[session] user=%s has no github token — skipping push", user_id)
            return

        svc = GitHubStorageService(user.github_access_token, user.github_username)
        await svc.ensure_repo()

        # Include AI gap analysis in the session JSON so it's visible in the journal
        session_data["gap_analysis"] = gap_analysis
        committed = await svc.commit_session(session_data)
        log.info("[session] session commit=%s for %s", committed, q)

        # Step 3 — generate and commit AI insight markdown
        if not has_api_key():
            log.info("[session] ANTHROPIC_API_KEY not set — skipping insight")
        elif committed:
            try:
                insight_md = await generate_session_insight(session_data)
                ok = await svc.commit_insight(insight_md, session_data["date"], q)
                log.info("[session] insight commit=%s for %s", ok, q)
            except Exception as ie:
                log.warning("[session] insight skipped for %s: %s", q, ie)

    except Exception as e:
        log.error("[session] validate+push failed for user=%s qid=%s: %s", user_id, qid, e, exc_info=True)


@router.get("/activity")
async def get_activity(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
    tz: str = "UTC",
):
    return await crud.get_activity(db, user_id, tz=tz)


@router.get("/questions")
async def get_all(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.get_questions(db, user_id)


@router.post("/questions")
async def create(
    q: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(require_admin),
):
    return await crud.create_question(db, q, user_id)


@router.put("/questions/{qid}")
async def update(
    qid: int,
    q: QuestionCreate,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(require_admin),
):
    return await crud.update_question(db, qid, q, user_id)


@router.post("/questions/{qid}/log")
async def add_log(
    qid: int,
    log: dict,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    result = await crud.add_log(db, qid, log, user_id)

    # Build the session payload for GitHub
    latest = result["logs"][-1] if result.get("logs") else {}
    session_data = {
        "date":               latest.get("date", ""),
        "question":           result.get("title", ""),
        "pattern":            result.get("pattern", ""),
        "category":           result.get("category", ""),
        "difficulty":         result.get("difficulty", ""),
        "correct":            log.get("correct", True),
        "time_taken_seconds": latest.get("time_taken", 0),
        "logic":              latest.get("logic", ""),
        "code":               latest.get("code", ""),
    }
    background_tasks.add_task(_validate_then_push, user_id, qid, session_data)

    return result


@router.put("/questions/{qid}/status")
async def update_status(
    qid: int,
    category: str = Body(...),
    coverage_status: str = Body(...),
    revision_status: str = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.update_question_status(db, qid, category, coverage_status, revision_status, user_id)


@router.patch("/questions/{qid}/notes")
async def update_notes(
    qid: int,
    notes: str = Body(""),
    my_gap_analysis: str = Body(""),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.update_notes(db, qid, notes, my_gap_analysis, user_id)


@router.get("/questions/{qid}/last-log")
async def get_last_log(
    qid: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    record = await crud.get_last_log(db, qid, user_id)
    if record is None:
        raise HTTPException(status_code=404, detail="No log found")
    return record


@router.patch("/questions/{qid}/last-log")
async def update_last_log(
    qid: int,
    logic: str = Body(""),
    code: str = Body(""),
    notes: str = Body(""),
    my_gap_analysis: str = Body(""),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.update_last_log(db, qid, user_id, logic, code, notes, my_gap_analysis)


@router.post("/questions/{qid}/validate")
async def validate(
    qid: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.validate_question(db, qid, user_id)


@router.post("/upload_md")
async def upload_md(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
):
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are supported.")
    content = (await file.read()).decode("utf-8")
    added, total = await crud.add_questions_from_md(db, content)
    return {"added": added, "total": total}


@router.patch("/me/practice-days")
async def update_practice_days(
    practice_days: str = Body(..., embed=True),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """
    practice_days: comma-separated weekday numbers (0=Mon … 6=Sun), e.g. "0,2,4".
    Send empty string "" to switch back to daily.
    """
    if practice_days:
        try:
            parsed = [int(d) for d in practice_days.split(",") if d.strip()]
            if not all(0 <= d <= 6 for d in parsed):
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="practice_days must be comma-separated weekday numbers 0-6")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.practice_days = practice_days
    await db.commit()
    updated = await crud.recalculate_next_revisions(db, user_id, practice_days)
    return {"practice_days": practice_days, "revisions_updated": updated}


@router.get("/me/practice-days")
async def get_practice_days(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    return {"practice_days": user.practice_days if user else ""}


@router.post("/github/setup")
async def github_setup(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Ensure the user's private dsa-planner-data repo exists (idempotent)."""
    from backend.db.models import User as UserModel
    from backend.services.github_storage import GitHubStorageService

    user = await db.get(UserModel, user_id)
    if not user or not user.github_access_token or not user.github_username:
        return {"ok": False, "reason": "no_github_token"}

    svc = GitHubStorageService(user.github_access_token, user.github_username)
    created = await svc.ensure_repo()
    return {"ok": created}


@router.get("/github/history")
async def github_history(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Return all practice sessions + AI insights from the user's private GitHub repo."""
    from backend.db.models import User as UserModel
    from backend.services.github_storage import GitHubStorageService

    user = await db.get(UserModel, user_id)
    if not user or not user.github_access_token or not user.github_username:
        return {"connected": False, "sessions": []}

    svc = GitHubStorageService(user.github_access_token, user.github_username)
    sessions = await svc.list_sessions_with_insights()
    return {"connected": True, "sessions": sessions}


@router.post("/sync_questions")
async def sync_questions(
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
):
    added = await crud.sync_questions_from_file(db)
    return {"status": f"Synced {added} new questions from DSA_Must_Solve_Problems.md"}
