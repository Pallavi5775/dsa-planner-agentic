"""
Orchestrator Agent.

The boss agent. Receives a high-level goal, runs specialist agents
in parallel or sequentially, collects results, and produces a
combined final output.

Specialist agents:
  - Session Analyst  (agent.py)         — analyzes practice sessions
  - Study Coach      (agent.py)         — plans daily study
  - SharePoint Lib   (sharepoint_agent) — saves files to OneDrive
  - Teams Notifier   (teams_agent)      — sends Teams messages
  - Calendar Sched   (calendar_agent)   — creates Outlook events
"""

import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger(__name__)


# ── Orchestration scenarios ─────────────────────────────────────────────────────

async def run_post_session_pipeline(
    user_id: int,
    session_data: dict,
    ms_access_token: str | None = None,
    ms_refresh_token: str | None = None,
    teams_webhook: str | None = None,
) -> dict:
    """
    Run after a practice session is logged.

    Pipeline (sequential steps, each feeds the next):
      1. Session Analyst  → generates personalized insight
      2. SharePoint Lib   → saves session + insight to OneDrive (if MS connected)
      3. Teams Notifier   → sends insight summary to Teams (if configured)

    Returns dict with results from each step.
    """
    results = {}

    # Step 1: Session Analyst — runs first, produces the insight
    log.info("[orchestrator] post-session: running session analyst for user=%s", user_id)
    try:
        from backend.services.agent import agentic_session_insight
        insight_md = await agentic_session_insight(session_data, user_id)
        results["insight"] = insight_md
        log.info("[orchestrator] insight generated (%d chars)", len(insight_md))
    except Exception as e:
        log.error("[orchestrator] session analyst failed: %s", e)
        results["insight"] = ""

    # Step 2: SharePoint Librarian — save session + insight to OneDrive
    if ms_access_token:
        log.info("[orchestrator] post-session: saving to SharePoint for user=%s", user_id)
        try:
            from backend.services.sharepoint_agent import run_sharepoint_librarian
            sp_result = await run_sharepoint_librarian(
                user_id=user_id,
                access_token=ms_access_token,
                refresh_token=ms_refresh_token or "",
                goal="Save the practice session and AI insight to SharePoint/OneDrive",
                extra_context={
                    "session": session_data,
                    "insight_md": results["insight"],
                },
            )
            results["sharepoint"] = sp_result
        except Exception as e:
            log.error("[orchestrator] sharepoint save failed: %s", e)
            results["sharepoint"] = f"error: {e}"

    # Step 3: Teams Notifier — send a summary (non-blocking; best effort)
    if teams_webhook and results.get("insight"):
        log.info("[orchestrator] post-session: sending Teams notification")
        try:
            from backend.services.teams_agent import run_teams_notifier
            summary = results["insight"][:300] + "…" if len(results["insight"]) > 300 else results["insight"]
            teams_result = await run_teams_notifier(
                message=summary,
                webhook_url=teams_webhook,
                title=f"DSA Session — {session_data.get('question', '')}",
            )
            results["teams"] = teams_result
        except Exception as e:
            log.warning("[orchestrator] teams notification failed: %s", e)
            results["teams"] = f"error: {e}"

    return results


async def run_weekly_review_pipeline(
    user_id: int,
    username: str,
    sessions: list[dict],
    ms_access_token: str | None = None,
    ms_refresh_token: str | None = None,
    teams_webhook: str | None = None,
    schedule_calendar: bool = False,
) -> dict:
    """
    Run the end-of-week review.

    Runs Study Coach and Session Analyst IN PARALLEL, then fans out to
    SharePoint (save), Teams (notify), Calendar (schedule next week).

    Returns dict with results from all agents.
    """
    today = datetime.now(timezone.utc)
    week_label = f"{today.year}-W{today.isocalendar()[1]:02d}"
    results = {"week_label": week_label}

    # Phase 1: Study Coach + Weekly Summary Analyst in PARALLEL
    log.info("[orchestrator] weekly review: running agents in parallel for user=%s", user_id)
    try:
        from backend.services.agent import agentic_weekly_summary, agentic_study_coach
        summary_task = agentic_weekly_summary(sessions, username, user_id)
        coach_task   = agentic_study_coach(user_id, username)
        summary_md, coach_plan = await asyncio.gather(summary_task, coach_task)
        results["weekly_summary"] = summary_md
        results["study_plan"] = coach_plan
        log.info("[orchestrator] parallel agents done")
    except Exception as e:
        log.error("[orchestrator] weekly agents failed: %s", e)
        results["weekly_summary"] = ""
        results["study_plan"] = ""

    # Phase 2: Fan-out — SharePoint + Teams + Calendar in PARALLEL
    fan_out_tasks = []

    if ms_access_token and results["weekly_summary"]:
        async def _save_to_sharepoint():
            from backend.services.sharepoint_agent import run_sharepoint_librarian
            return await run_sharepoint_librarian(
                user_id=user_id,
                access_token=ms_access_token,
                refresh_token=ms_refresh_token or "",
                goal="Save the weekly summary markdown to SharePoint",
                extra_context={"summary_md": results["weekly_summary"], "week_label": week_label},
            )
        fan_out_tasks.append(("sharepoint", _save_to_sharepoint()))

    if teams_webhook and (results["weekly_summary"] or results["study_plan"]):
        async def _notify_teams():
            from backend.services.teams_agent import run_teams_notifier
            msg = results["study_plan"] or results["weekly_summary"][:400]
            return await run_teams_notifier(
                message=msg,
                webhook_url=teams_webhook,
                title=f"Weekly DSA Review — {week_label}",
            )
        fan_out_tasks.append(("teams", _notify_teams()))

    if schedule_calendar and ms_access_token:
        async def _schedule_calendar():
            from backend.services.calendar_agent import run_calendar_scheduler
            from backend.services.agent import _tool_get_due_questions
            due = await _tool_get_due_questions(user_id, days_ahead=7)
            return await run_calendar_scheduler(user_id, ms_access_token, due)
        fan_out_tasks.append(("calendar", _schedule_calendar()))

    if fan_out_tasks:
        log.info("[orchestrator] running %d fan-out tasks in parallel", len(fan_out_tasks))
        task_results = await asyncio.gather(*[t for _, t in fan_out_tasks], return_exceptions=True)
        for (name, _), result in zip(fan_out_tasks, task_results):
            results[name] = str(result) if isinstance(result, Exception) else result

    return results


async def run_daily_coaching_pipeline(
    user_id: int,
    username: str,
    ms_access_token: str | None = None,
    ms_refresh_token: str | None = None,
    teams_webhook: str | None = None,
    schedule_calendar: bool = False,
) -> dict:
    """
    Run the daily study coaching pipeline.

    Study Coach + Calendar Scheduler in PARALLEL,
    then Teams notifier with the combined plan.
    """
    results = {}

    # Phase 1: Coach + Calendar in PARALLEL
    from backend.services.agent import agentic_study_coach, _tool_get_due_questions

    async def _coach():
        return await agentic_study_coach(user_id, username)

    async def _due_questions():
        return await _tool_get_due_questions(user_id, days_ahead=3)

    tasks = [_coach(), _due_questions()]
    coach_plan, due_questions = await asyncio.gather(*tasks, return_exceptions=True)
    results["study_plan"] = coach_plan if not isinstance(coach_plan, Exception) else ""
    results["due_questions"] = due_questions if not isinstance(due_questions, Exception) else []

    # Phase 2: Calendar scheduling
    if schedule_calendar and ms_access_token and results["due_questions"]:
        try:
            from backend.services.calendar_agent import run_calendar_scheduler
            cal_result = await run_calendar_scheduler(
                user_id, ms_access_token, results["due_questions"]
            )
            results["calendar"] = cal_result
        except Exception as e:
            log.warning("[orchestrator] calendar scheduling failed: %s", e)
            results["calendar"] = f"error: {e}"

    # Phase 3: Teams notification
    if teams_webhook and results.get("study_plan"):
        try:
            from backend.services.teams_agent import run_teams_notifier
            await run_teams_notifier(
                message=results["study_plan"],
                webhook_url=teams_webhook,
                title="Today's DSA Study Plan",
            )
            results["teams_sent"] = True
        except Exception as e:
            log.warning("[orchestrator] teams daily notification failed: %s", e)
            results["teams_sent"] = False

    return results
