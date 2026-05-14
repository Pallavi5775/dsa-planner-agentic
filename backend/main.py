import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.routes import router
from backend.api.auth import router as auth_router
from backend.api.notification_routes import router as notif_router
from backend.api.microsoft_auth import router as ms_auth_router

log = logging.getLogger(__name__)


async def _run_weekly_summaries() -> None:
    """
    Weekly review pipeline for all users.

    Storage priority (enterprise pattern):
      1. SharePoint / OneDrive — primary source + destination
      2. GitHub                — fallback only if no Microsoft token
    """
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.db.models import User
        from backend.services.ai_insights import has_api_key
        from sqlalchemy.future import select

        if not has_api_key():
            return

        today = datetime.now(timezone.utc)
        week_label = f"{today.year}-W{today.isocalendar()[1]:02d}"

        async with AsyncSessionLocal() as db:
            all_users = (await db.execute(select(User))).scalars().all()
            # Microsoft users first, then GitHub-only users
            ms_users  = [u for u in all_users if u.microsoft_access_token]
            gh_users  = [u for u in all_users if not u.microsoft_access_token
                         and u.github_access_token and u.github_username]
            users = ms_users + gh_users

        for user in users:
            try:
                week_sessions = []

                # Primary: load sessions from SharePoint
                if user.microsoft_access_token:
                    from backend.services.sharepoint_storage import SharePointStorageService
                    sp = SharePointStorageService(user.microsoft_access_token, user.microsoft_refresh_token)
                    all_sessions = await sp.list_session_files()
                    week_sessions = [
                        s for s in all_sessions
                        if s.get("date", "").startswith(str(today.year))
                        and _iso_week(s.get("date", "")) == today.isocalendar()[1]
                    ]

                # Fallback: load from GitHub if no Microsoft
                if not week_sessions and user.github_access_token and user.github_username:
                    from backend.services.github_storage import GitHubStorageService
                    gh = GitHubStorageService(user.github_access_token, user.github_username)
                    all_sessions = await gh.list_session_files()
                    week_sessions = [
                        s for s in all_sessions
                        if s.get("date", "").startswith(str(today.year))
                        and _iso_week(s.get("date", "")) == today.isocalendar()[1]
                    ]

                if not week_sessions:
                    continue

                # Run orchestrator pipeline (saves summary to SharePoint, sends Teams, schedules Calendar)
                from backend.services.orchestrator import run_weekly_review_pipeline
                results = await run_weekly_review_pipeline(
                    user_id=user.id,
                    username=user.username,
                    sessions=week_sessions,
                    ms_access_token=user.microsoft_access_token,
                    ms_refresh_token=user.microsoft_refresh_token,
                    teams_webhook=user.teams_webhook_url,
                    schedule_calendar=bool(user.microsoft_access_token),
                )

                # GitHub fallback: commit summary if no Microsoft
                summary_md = results.get("weekly_summary", "")
                if summary_md and not user.microsoft_access_token \
                        and user.github_access_token and user.github_username:
                    from backend.services.github_storage import GitHubStorageService
                    gh = GitHubStorageService(user.github_access_token, user.github_username)
                    await gh.commit_weekly_summary(summary_md, week_label)

                log.info("Weekly review pipeline done for user=%s", user.username)
            except Exception as e:
                log.warning("Weekly summary failed for user=%s: %s", user.username, e)
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


async def _run_daily_notifications() -> None:
    """Send daily digest notifications to users whose notify_hour matches the current UTC hour."""
    try:
        from backend.db.session import AsyncSessionLocal
        from backend.db.models import User, UserQuestionProgress, PracticeLog
        from backend.services.notifications import notify_user
        from backend.services.ai_insights import has_api_key
        from sqlalchemy.future import select

        now = datetime.now(timezone.utc)
        today_str = now.date().isoformat()
        yesterday_str = (now.date() - timedelta(days=1)).isoformat()

        async with AsyncSessionLocal() as db:
            users = (await db.execute(
                select(User).where(User.notify_hour == now.hour)
            )).scalars().all()

            for user in users:
                # Skip if already notified today
                if user.last_notif_date == today_str:
                    continue
                try:
                    messages: list[tuple[str, str]] = []

                    # Pending revisions count
                    pending_count = len((await db.execute(
                        select(UserQuestionProgress).where(
                            UserQuestionProgress.user_id == user.id,
                            UserQuestionProgress.next_revision.isnot(None),
                            UserQuestionProgress.next_revision <= today_str,
                        )
                    )).scalars().all())
                    if pending_count:
                        noun = "revision" if pending_count == 1 else "revisions"
                        messages.append((
                            f"📚 {pending_count} {noun} pending today — open the planner to keep your streak alive!",
                            "revisions",
                        ))

                    # Streak warning: no practice today AND no practice yesterday
                    had_today = bool((await db.execute(
                        select(PracticeLog).where(
                            PracticeLog.user_id == user.id,
                            PracticeLog.date == today_str,
                        ).limit(1)
                    )).scalar_one_or_none())

                    had_yesterday = bool((await db.execute(
                        select(PracticeLog).where(
                            PracticeLog.user_id == user.id,
                            PracticeLog.date == yesterday_str,
                        ).limit(1)
                    )).scalar_one_or_none())

                    if not had_today and not had_yesterday:
                        messages.append((
                            "🔥 You're losing your streak! No practice logged today or yesterday. Jump back in now!",
                            "streak",
                        ))

                    # Agentic study coach: personalized plan replaces the generic revision count message
                    if has_api_key():
                        try:
                            from backend.services.agent import agentic_study_coach
                            coach_msg = await agentic_study_coach(user.id, user.username)
                            if coach_msg:
                                # Replace the generic revision-count message with the agent's plan
                                messages = [(m, t) for m, t in messages if t != "revisions"]
                                messages.insert(0, (coach_msg, "revisions"))
                        except Exception as ce:
                            log.warning("Study coach failed for user_id=%s: %s", user.id, ce)

                    for message, notif_type in messages:
                        await notify_user(db, user, message, notif_type)

                    user.last_notif_date = today_str
                    await db.commit()

                except Exception as e:
                    log.warning("Daily notification failed for user_id=%s: %s", user.id, e)

    except Exception as e:
        log.error("Daily notification worker error: %s", e)


async def _notification_worker() -> None:
    """Wake up every hour to dispatch daily digest notifications."""
    while True:
        await asyncio.sleep(3600)
        log.debug("Running daily notification check…")
        await _run_daily_notifications()


@asynccontextmanager
async def lifespan(_: FastAPI):
    asyncio.create_task(_weekly_worker())
    asyncio.create_task(_notification_worker())
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
app.include_router(ms_auth_router, prefix="/api")
app.include_router(router, prefix="/api")
app.include_router(notif_router, prefix="/api")
