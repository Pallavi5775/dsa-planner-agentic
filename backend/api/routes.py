import logging
from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
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
    """
    Background task: AI-validate the session, then run the post-session
    orchestrator pipeline.

    Storage priority (enterprise pattern):
      1. SharePoint / OneDrive  — primary (Microsoft login)
      2. GitHub                 — optional fallback (if connected)
    """
    q = session_data.get("question", "?")
    log.info("[session] starting validate+push for user=%s qid=%s", user_id, qid)
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.db.models import User as UserModel
        from backend.services.ai_insights import has_api_key

        # Step 1 — AI validate: saves accuracy/suggestions/revision_status to DB
        gap_analysis = ""
        try:
            async with AsyncSessionLocal() as db:
                result = await crud.validate_question(db, qid, user_id)
            gap_analysis = result.get("gap_analysis", "") if result else ""
            log.info("[session] validate done for qid=%s correct=%s", qid, result.get("correct") if result else "no-result")
        except Exception as ve:
            log.error("[session] validate failed for qid=%s: %s", qid, ve, exc_info=True)

        session_data["gap_analysis"] = gap_analysis

        async with AsyncSessionLocal() as db:
            user = await db.get(UserModel, user_id)

        # Step 2 — SharePoint (primary enterprise storage)
        if user and user.microsoft_access_token:
            try:
                from backend.services.sharepoint_storage import SharePointStorageService
                sp = SharePointStorageService(user.microsoft_access_token, user.microsoft_refresh_token)
                committed = await sp.commit_session(session_data)
                log.info("[session] sharepoint commit=%s for %s", committed, q)
            except Exception as se:
                log.warning("[session] sharepoint commit failed: %s", se)

        # Step 3 — Orchestrator pipeline (agentic insight + Teams notification)
        if has_api_key():
            try:
                from backend.services.orchestrator import run_post_session_pipeline
                results = await run_post_session_pipeline(
                    user_id=user_id,
                    session_data=session_data,
                    ms_access_token=user.microsoft_access_token if user else None,
                    ms_refresh_token=user.microsoft_refresh_token if user else None,
                    teams_webhook=user.teams_webhook_url if user else None,
                )
                log.info("[session] orchestrator pipeline done for %s", q)
            except Exception as oe:
                log.error("[session] orchestrator failed: %s", oe, exc_info=True)

        # Step 4 — GitHub (optional fallback — only if no Microsoft token)
        if user and user.github_access_token and user.github_username and not user.microsoft_access_token:
            try:
                from backend.services.github_storage import GitHubStorageService
                svc = GitHubStorageService(user.github_access_token, user.github_username)
                await svc.ensure_repo()
                await svc.commit_session(session_data)
                log.info("[session] github fallback commit done for %s", q)
            except Exception as ge:
                log.warning("[session] github fallback failed: %s", ge)

        # Step 4 — mastery notification
        try:
            pattern = session_data.get("pattern", "")
            if pattern and user:
                from backend.db.models import UserQuestionProgress, Question as QuestionModel
                from backend.services.notifications import notify_user
                from sqlalchemy.future import select as sa_select

                async with AsyncSessionLocal() as db:
                    rows = (await db.execute(
                        sa_select(UserQuestionProgress)
                        .join(QuestionModel, UserQuestionProgress.question_id == QuestionModel.id)
                        .where(
                            UserQuestionProgress.user_id == user_id,
                            QuestionModel.pattern == pattern,
                            UserQuestionProgress.accuracy.isnot(None),
                        )
                    )).scalars().all()

                    if rows:
                        avg_acc = round(sum(r.accuracy for r in rows) / len(rows))
                        msg = f"🏆 *{pattern}* mastery updated to *{avg_acc}%* across {len(rows)} question{'s' if len(rows) != 1 else ''}."
                        await notify_user(db, user, msg, "mastery")
                        log.info("[session] mastery notif sent: pattern=%s acc=%s%%", pattern, avg_acc)
        except Exception as me:
            log.warning("[session] mastery notification failed: %s", me)

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
        "question_id":        qid,
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


@router.patch("/questions/{qid}/hint")
async def update_hint(
    qid: int,
    hint: str = Body(""),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(require_admin),
):
    from backend.db.models import Question as QuestionModel
    q = (await db.execute(select(QuestionModel).where(QuestionModel.id == qid))).scalar_one_or_none()
    if q is None:
        raise HTTPException(status_code=404, detail="Question not found")
    q.hint = hint or None
    await db.commit()
    return {"status": "ok"}


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


@router.post("/questions/{qid}/variation-review")
async def variation_review(
    qid: int,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.variation_review(
        db, qid,
        variation_title=body.get("variation_title", ""),
        variation_description=body.get("variation_description", ""),
        code=body.get("code", ""),
        notes=body.get("notes", ""),
    )


@router.post("/questions/{qid}/description")
async def get_or_generate_description(
    qid: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.generate_question_description(db, qid)


@router.post("/questions/{qid}/validate")
async def validate(
    qid: int,
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.validate_question(db, qid, user_id)


@router.post("/questions/{qid}/chat")
async def hint_chat(
    qid: int,
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.hint_chat(
        db, qid,
        message=body.get("message", ""),
        context=body.get("context", {}),
        history=body.get("history", []),
        generate_variations=body.get("generate_variations", False),
    )


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


@router.post("/upload_md/agentic")
async def upload_md_agentic(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
):
    """
    Agentic markdown import.

    An AI agent reads the file, checks for duplicates, classifies each question
    (pattern, difficulty, category), generates a hint, imports everything,
    and returns a rich report of what was added and what was skipped.
    """
    if not file.filename.endswith(".md"):
        raise HTTPException(status_code=400, detail="Only .md files are supported.")

    import os
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENAI_API_KEY not configured.")

    content = (await file.read()).decode("utf-8")

    from backend.services.admin_agent import run_admin_upload_agent
    report = await run_admin_upload_agent(content, db)
    return report


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
    from backend.db.models import User as UserModel
    from backend.services.github_storage import GitHubStorageService

    user = await db.get(UserModel, user_id)
    if not user or not user.github_access_token or not user.github_username:
        return {"connected": False, "sessions": []}

    svc = GitHubStorageService(user.github_access_token, user.github_username)
    sessions = await svc.list_sessions_with_insights()
    return {"connected": True, "sessions": sessions}


@router.get("/sharepoint/history")
async def sharepoint_history(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    """Return all practice sessions + AI insights from the user's OneDrive."""
    from backend.db.models import User as UserModel
    from backend.services.sharepoint_storage import SharePointStorageService

    user = await db.get(UserModel, user_id)
    if not user or not user.microsoft_access_token:
        return {"connected": False, "sessions": []}

    svc = SharePointStorageService(user.microsoft_access_token, user.microsoft_refresh_token)
    sessions = await svc.list_sessions_with_insights()
    return {"connected": True, "sessions": sessions}


@router.get("/pattern-notes")
async def get_pattern_notes(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.get_all_pattern_notes(db, user_id)


@router.patch("/pattern-notes")
async def update_pattern_notes(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.update_pattern_note(
        db, user_id,
        pattern=body.get("pattern", ""),
        notes=body.get("notes"),
        memory_techniques=body.get("memory_techniques"),
    )


@router.post("/pattern-chat")
async def pattern_chat_endpoint(
    body: dict = Body(...),
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.pattern_chat(
        db,
        pattern=body.get("pattern", ""),
        message=body.get("message", ""),
        generate_memo=body.get("generate_memo", False),
    )


@router.post("/sync_questions")
async def sync_questions(
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
):
    added = await crud.sync_questions_from_file(db)
    return {"status": f"Synced {added} new questions from DSA_Must_Solve_Problems.md"}


# ── Admin: user management ─────────────────────────────────────────────────────

class _UserCreate(BaseModel):
    email: str
    username: str | None = None
    role: str = "user"


@router.post("/users", status_code=201)
async def admin_create_user(
    body: _UserCreate,
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
):
    """Admin-only: pre-register a user by email. They can then log in via OAuth."""
    from backend.crud.user import _sanitize_username, _unique_username

    existing = (await db.execute(select(User).where(User.email == body.email))).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="A user with that email already exists")

    base = _sanitize_username(body.username or body.email.split("@")[0])
    safe_username = await _unique_username(db, base)
    user = User(
        username=safe_username,
        email=body.email,
        hashed_password=None,
        oauth_provider=None,
        oauth_id=None,
        role=body.role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return {"id": user.id, "username": user.username, "email": user.email, "role": user.role}


@router.get("/admin/agent-logs")
async def get_agent_logs(
    limit: int = 100,
    _: int = Depends(require_admin),
):
    """Return recent agent activity log entries from in-memory buffer."""
    from backend.services.agent_logger import get_logs
    return {"logs": get_logs(limit)}


@router.delete("/admin/agent-logs")
async def clear_agent_logs(_: int = Depends(require_admin)):
    """Clear the in-memory agent log buffer."""
    from backend.services.agent_logger import clear_logs
    clear_logs()
    return {"status": "cleared"}


@router.get("/admin/question-count")
async def admin_question_count(
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
):
    """Admin debug: return raw count of questions in dsa.questions table."""
    from backend.db.models import Question as QuestionModel
    count = len((await db.execute(select(QuestionModel))).scalars().all())
    return {"count": count}


@router.get("/users")
async def admin_list_users(
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
):
    """Admin-only: list all registered users."""
    users = (await db.execute(select(User))).scalars().all()
    return [
        {"id": u.id, "username": u.username, "email": u.email, "role": u.role,
         "oauth_provider": u.oauth_provider}
        for u in users
    ]


@router.delete("/users/{uid}", status_code=204)
async def admin_delete_user(
    uid: int,
    db: AsyncSession = Depends(get_db),
    admin_id: int = Depends(require_admin),
):
    """Admin-only: delete a user account."""
    if uid == admin_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")
    user = (await db.execute(select(User).where(User.id == uid))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    await db.delete(user)
    await db.commit()
