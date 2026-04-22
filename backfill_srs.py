"""
One-time backfill: recalculates interval/ease/next_revision from scratch
using each user's practice_days setting.
"""
import asyncio
from sqlalchemy.future import select
from backend.db.session import AsyncSessionLocal
from backend.db.models import PracticeLog, UserQuestionProgress, User
from backend.core.utils import get_spaced_repetition_values, compute_next_revision


async def backfill():
    async with AsyncSessionLocal() as db:
        users = (await db.execute(select(User))).scalars().all()
        practice_days_by_uid = {u.id: u.practice_days for u in users}

        all_logs = (await db.execute(select(PracticeLog))).scalars().all()

        logs_by_user_question: dict[tuple, list] = {}
        for log in all_logs:
            logs_by_user_question.setdefault((log.user_id, log.question_id), []).append(log)

        updated = 0
        for (user_id, question_id), logs in logs_by_user_question.items():
            progress = (await db.execute(
                select(UserQuestionProgress).where(
                    UserQuestionProgress.user_id == user_id,
                    UserQuestionProgress.question_id == question_id,
                )
            )).scalar_one_or_none()

            if progress is None:
                progress = UserQuestionProgress(user_id=user_id, question_id=question_id)
                db.add(progress)
                await db.flush()

            # Simulate history from scratch
            ease, interval = 2.5, 0
            for log in sorted(logs, key=lambda l: l.date):
                interval, ease = get_spaced_repetition_values([log], ease, interval)

            practice_days = practice_days_by_uid.get(user_id, "")
            last_log_date = max(log.date for log in logs)
            progress.interval_days = interval
            progress.ease_factor = round(ease, 4)
            progress.next_revision = compute_next_revision(last_log_date, interval, practice_days)
            updated += 1
            days_label = f"days={practice_days}" if practice_days else "daily"
            print(f"  user={user_id} q={question_id} [{days_label}] interval={interval} ease={ease:.2f} next={progress.next_revision}")

        await db.commit()
        print(f"\nBackfill complete: {updated} records updated.")


if __name__ == "__main__":
    asyncio.run(backfill())
