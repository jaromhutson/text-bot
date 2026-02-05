from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import settings
from app.database import get_db


async def create_plan(name: str, plan_type: str = "gtm", description: str | None = None) -> dict:
    db = await get_db()
    cursor = await db.execute(
        "INSERT INTO plans (name, type, description) VALUES (?, ?, ?)",
        (name, plan_type, description),
    )
    await db.commit()
    row = await db.execute_fetchall("SELECT * FROM plans WHERE id=?", (cursor.lastrowid,))
    return dict(row[0])


async def get_plan(plan_id: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall("SELECT * FROM plans WHERE id=?", (plan_id,))
    return dict(rows[0]) if rows else None


async def list_plans(status: str | None = None) -> list[dict]:
    db = await get_db()
    if status:
        rows = await db.execute_fetchall(
            "SELECT * FROM plans WHERE status=? ORDER BY id", (status,)
        )
    else:
        rows = await db.execute_fetchall("SELECT * FROM plans ORDER BY id")
    return [dict(r) for r in rows]


async def activate_plan(plan_id: int, start_date: str) -> int:
    """Set scheduled dates for all tasks/phases based on start_date + day_offset."""
    db = await get_db()
    start = datetime.strptime(start_date, "%Y-%m-%d")

    # Update phase dates
    phases = await db.execute_fetchall(
        "SELECT id, phase_number FROM phases WHERE plan_id=? ORDER BY phase_number",
        (plan_id,),
    )
    for phase in phases:
        week_start = start + timedelta(weeks=phase["phase_number"] - 1)
        week_end = week_start + timedelta(days=6)
        await db.execute(
            "UPDATE phases SET start_date=?, end_date=?, status='upcoming' WHERE id=?",
            (week_start.strftime("%Y-%m-%d"), week_end.strftime("%Y-%m-%d"), phase["id"]),
        )

    # Set first phase to active
    await db.execute(
        "UPDATE phases SET status='active' WHERE plan_id=? AND phase_number=1",
        (plan_id,),
    )

    # Update all task scheduled dates
    tasks = await db.execute_fetchall(
        "SELECT id, day_offset FROM tasks WHERE plan_id=?", (plan_id,)
    )
    for task in tasks:
        scheduled = start + timedelta(days=task["day_offset"])
        await db.execute(
            "UPDATE tasks SET scheduled_date=?, status='pending' WHERE id=?",
            (scheduled.strftime("%Y-%m-%d"), task["id"]),
        )

    # Update plan record
    last_task = await db.execute_fetchall(
        "SELECT MAX(day_offset) as max_offset FROM tasks WHERE plan_id=?", (plan_id,)
    )
    end_offset = last_task[0]["max_offset"] if last_task and last_task[0]["max_offset"] else 0
    end_date = (start + timedelta(days=end_offset)).strftime("%Y-%m-%d")

    await db.execute(
        "UPDATE plans SET status='active', start_date=?, end_date=?, updated_at=datetime('now') WHERE id=?",
        (start_date, end_date, plan_id),
    )

    # Save to bot_settings for backward compat
    await db.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('plan_start_date', ?)",
        (start_date,),
    )
    await db.execute(
        "INSERT OR REPLACE INTO bot_settings (key, value) VALUES ('plan_status', 'active')",
    )
    await db.commit()

    return len(tasks)


async def complete_plan(plan_id: int) -> dict | None:
    db = await get_db()
    await db.execute(
        "UPDATE plans SET status='completed', updated_at=datetime('now') WHERE id=?",
        (plan_id,),
    )
    await db.commit()
    return await get_plan(plan_id)


async def archive_plan(plan_id: int) -> dict | None:
    db = await get_db()
    await db.execute(
        "UPDATE plans SET status='archived', updated_at=datetime('now') WHERE id=?",
        (plan_id,),
    )
    await db.commit()
    return await get_plan(plan_id)


async def get_current_plan() -> dict | None:
    """Return the active plan, or fall back to the default plan."""
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM plans WHERE status='active' ORDER BY id LIMIT 1"
    )
    if rows:
        return dict(rows[0])
    # Fall back to default_plan_id
    rows = await db.execute_fetchall(
        "SELECT * FROM plans WHERE id=?", (settings.default_plan_id,)
    )
    return dict(rows[0]) if rows else None
