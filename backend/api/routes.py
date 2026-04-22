from fastapi import APIRouter, Depends, HTTPException, Body, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.db.session import get_db
from backend.db.models import User
from backend.crud import question as crud
from backend.schemas.question import QuestionCreate
from backend.core.security import get_current_user_id, require_admin

router = APIRouter()


@router.get("/activity")
async def get_activity(
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.get_activity(db, user_id)


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
    db: AsyncSession = Depends(get_db),
    user_id: int = Depends(get_current_user_id),
):
    return await crud.add_log(db, qid, log, user_id)


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


@router.post("/sync_questions")
async def sync_questions(
    db: AsyncSession = Depends(get_db),
    _: int = Depends(require_admin),
):
    added = await crud.sync_questions_from_file(db)
    return {"status": f"Synced {added} new questions from DSA_Must_Solve_Problems.md"}
