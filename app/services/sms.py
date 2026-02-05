from __future__ import annotations

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from twilio.rest import Client

from app.config import settings
from app.database import get_db
from app.services.tasks import get_tasks_for_date, get_plan_stats

logger = logging.getLogger(__name__)


def get_twilio_client() -> Client:
    return Client(settings.twilio_account_sid, settings.twilio_auth_token)


def format_daily_sms(tasks: list[dict], date_str: str) -> str:
    """Format today's tasks into a concise SMS (plan-agnostic)."""
    if not tasks:
        return f"No tasks scheduled for {date_str}. Enjoy the break!"

    dt = datetime.strptime(date_str, "%Y-%m-%d")
    day_name = dt.strftime("%a %b %d")

    lines = [f"GM! {day_name}"]

    pending = [t for t in tasks if t["status"] == "pending"]
    completed = [t for t in tasks if t["status"] == "completed"]

    if completed:
        lines.append(f"({len(completed)} already done today)")

    if not pending:
        lines.append("All tasks done for today!")
    else:
        for t in pending:
            ai_tag = " [AI]" if t["execution_type"] == "agent_assisted" else ""
            time_est = f" ~{t['estimated_minutes']}m" if t["estimated_minutes"] else ""
            priority_marker = "!" if t["priority"] == 1 else ""
            lines.append(
                f"{priority_marker}{t['task_number']}. {t['title']}{ai_tag}{time_est}"
            )

    lines.append("\nReply with updates or questions!")

    msg = "\n".join(lines)
    if len(msg) > settings.sms_char_limit:
        msg = msg[: settings.sms_char_limit - 3] + "..."
    return msg


def format_weekly_review(stats: dict, upcoming: list[dict]) -> str:
    """Format weekly review SMS (plan-agnostic)."""
    lines = ["Weekly Review"]

    by_status = stats.get("by_status", {})
    lines.append(
        f"Done: {by_status.get('completed', 0)} | "
        f"Skipped: {by_status.get('skipped', 0)} | "
        f"Pending: {by_status.get('pending', 0)}"
    )

    if upcoming:
        lines.append(f"\nNext week preview ({len(upcoming)} tasks):")
        for t in upcoming[:5]:
            lines.append(f"- {t['title']}")
        if len(upcoming) > 5:
            lines.append(f"  ...and {len(upcoming) - 5} more")

    return "\n".join(lines)


async def send_sms(to: str, body: str) -> str:
    """Send an SMS via Twilio."""
    if not settings.twilio_account_sid:
        logger.info("[DEV SMS -> %s]: %s", to, body)
        return "dev_mode"

    client = get_twilio_client()
    message = client.messages.create(
        body=body,
        from_=settings.twilio_phone_number,
        to=to,
    )

    # Log to conversations
    db = await get_db()
    await db.execute(
        """INSERT INTO conversations (direction, channel, phone_number, content, twilio_sid)
           VALUES (?, 'sms', ?, ?, ?)""",
        ("outbound", to, body, message.sid),
    )
    await db.commit()

    return message.sid


async def send_daily_tasks(plan_id: int, date: str | None = None) -> str:
    """Send today's tasks via SMS (plan-scoped)."""
    if not date:
        tz = ZoneInfo(settings.timezone)
        date = datetime.now(tz).strftime("%Y-%m-%d")

    tasks = await get_tasks_for_date(plan_id, date)
    msg = format_daily_sms(tasks, date)
    sid = await send_sms(settings.user_phone, msg)
    return f"Sent {len(tasks)} tasks (sid: {sid})"


async def send_weekly_review(plan_id: int) -> str:
    """Send weekly review summary (plan-scoped)."""
    stats = await get_plan_stats(plan_id)

    tz = ZoneInfo(settings.timezone)
    today = datetime.now(tz)
    next_monday = today + timedelta(days=(7 - today.weekday()))
    next_sunday = next_monday + timedelta(days=6)

    db = await get_db()
    upcoming = await db.execute_fetchall(
        """SELECT * FROM tasks
           WHERE plan_id=? AND scheduled_date BETWEEN ? AND ?
           ORDER BY scheduled_date, priority""",
        (plan_id, next_monday.strftime("%Y-%m-%d"), next_sunday.strftime("%Y-%m-%d")),
    )
    upcoming = [dict(r) for r in upcoming]

    msg = format_weekly_review(stats, upcoming)
    sid = await send_sms(settings.user_phone, msg)
    return f"Weekly review sent (sid: {sid})"
