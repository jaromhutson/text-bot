from __future__ import annotations

import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import settings
from app.services.sms import send_daily_tasks, send_weekly_review

logger = logging.getLogger(__name__)

_scheduler: AsyncIOScheduler | None = None

DAY_MAP = {
    "mon": 0, "tue": 1, "wed": 2, "thu": 3,
    "fri": 4, "sat": 5, "sun": 6,
}


async def _daily_job() -> None:
    try:
        await send_daily_tasks(settings.default_plan_id)
        logger.info("Daily tasks SMS sent")
    except Exception:
        logger.exception("Failed to send daily tasks SMS")


async def _weekly_job() -> None:
    try:
        await send_weekly_review(settings.default_plan_id)
        logger.info("Weekly review SMS sent")
    except Exception:
        logger.exception("Failed to send weekly review SMS")


def setup_scheduler() -> AsyncIOScheduler:
    global _scheduler
    tz = ZoneInfo(settings.timezone)

    _scheduler = AsyncIOScheduler(timezone=tz)

    # Daily tasks — every day at configured time
    _scheduler.add_job(
        _daily_job,
        CronTrigger(
            hour=settings.daily_send_hour,
            minute=settings.daily_send_minute,
            timezone=tz,
        ),
        id="daily_tasks",
        replace_existing=True,
    )

    # Weekly review — on configured day at configured hour
    review_dow = DAY_MAP.get(settings.weekly_review_day.lower(), 6)  # default Sunday
    _scheduler.add_job(
        _weekly_job,
        CronTrigger(
            day_of_week=review_dow,
            hour=settings.weekly_review_hour,
            minute=0,
            timezone=tz,
        ),
        id="weekly_review",
        replace_existing=True,
    )

    _scheduler.start()
    logger.info(
        "Scheduler started — daily at %02d:%02d, weekly review %s at %02d:00 (%s)",
        settings.daily_send_hour,
        settings.daily_send_minute,
        settings.weekly_review_day,
        settings.weekly_review_hour,
        settings.timezone,
    )
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Scheduler shut down")
    _scheduler = None
