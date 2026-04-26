import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.api.auth import router as auth_router

log = logging.getLogger(__name__)


async def _run_weekly_summaries() -> None:
    """Generate and commit weekly summaries for every GitHub-connected user."""
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.db.models import User
        from backend.services.github_storage import GitHubStorageService
        from backend.services.ai_insights import generate_weekly_summary, has_api_key
        from sqlalchemy.future import select

        if not has_api_key():
            return

        today = datetime.now(timezone.utc)
        week_label = f"{today.year}-W{today.isocalendar()[1]:02d}"

        async with AsyncSessionLocal() as db:
            users = (
                await db.execute(
                    select(User).where(
                        User.github_access_token.isnot(None),
                        User.github_username.isnot(None),
                    )
                )
            ).scalars().all()

        for user in users:
            try:
                svc = GitHubStorageService(user.github_access_token, user.github_username)
                all_sessions = await svc.list_session_files()

                # Keep only this week's sessions
                week_sessions = [
                    s for s in all_sessions
                    if s.get("date", "").startswith(str(today.year))
                    and _iso_week(s.get("date", "")) == today.isocalendar()[1]
                ]
                if not week_sessions:
                    continue

                summary_md = await generate_weekly_summary(week_sessions, user.github_username)
                if summary_md:
                    await svc.commit_weekly_summary(summary_md, week_label)
            except Exception as e:
                log.warning("Weekly summary failed for %s: %s", user.github_username, e)
    except Exception as e:
        log.error("Weekly summary worker error: %s", e)


def _iso_week(date_str: str) -> int:
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").isocalendar()[1]
    except ValueError:
        return -1


async def _weekly_worker() -> None:
    """Wake up every 6 hours; run summaries on Sunday UTC."""
    while True:
        await asyncio.sleep(6 * 3600)
        if datetime.now(timezone.utc).weekday() == 6:  # Sunday
            log.info("Running weekly GitHub summaries…")
            await _run_weekly_summaries()


@asynccontextmanager
async def lifespan(_: FastAPI):
    asyncio.create_task(_weekly_worker())
    yield


app = FastAPI(title="DSA Revision Planner API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router, prefix="/api")
app.include_router(router, prefix="/api")
