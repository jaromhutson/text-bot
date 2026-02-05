from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.config import settings
from app.database import get_db
from app.models import TaskUpdate


async def get_tasks_for_date(plan_id: int, date: str | None, status: str | None = None) -> list[dict]:
    db = await get_db()
    if date:
        rows = await db.execute_fetchall(
            "SELECT * FROM tasks WHERE plan_id=? AND scheduled_date=? ORDER BY priority, task_number",
            (plan_id, date),
        )
    elif status:
        rows = await db.execute_fetchall(
            "SELECT * FROM tasks WHERE plan_id=? AND status=? ORDER BY scheduled_date, priority, task_number",
            (plan_id, status),
        )
    else:
        rows = await db.execute_fetchall(
            "SELECT * FROM tasks WHERE plan_id=? ORDER BY scheduled_date, priority, task_number",
            (plan_id,),
        )
    return [dict(r) for r in rows]


async def get_task(plan_id: int, task_number: int) -> dict | None:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM tasks WHERE plan_id=? AND task_number=?",
        (plan_id, task_number),
    )
    return dict(rows[0]) if rows else None


async def update_task(plan_id: int, task_number: int, update: TaskUpdate) -> dict | None:
    db = await get_db()
    task = await get_task(plan_id, task_number)
    if not task:
        return None

    # Build a single UPDATE with all changed fields
    fields = []
    params = []

    if update.status is not None:
        fields.append("status=?")
        params.append(update.status.value)
        if update.status.value == "completed":
            tz = ZoneInfo(settings.timezone)
            fields.append("completed_at=?")
            params.append(datetime.now(tz).isoformat())

    if update.notes is not None:
        existing = task.get("notes") or ""
        new_notes = f"{existing}\n{update.notes}".strip() if existing else update.notes
        fields.append("notes=?")
        params.append(new_notes)

    if update.scheduled_date is not None:
        fields.append("scheduled_date=?")
        params.append(update.scheduled_date)
        # Reset status to pending when rescheduling (unless explicitly set)
        if update.status is None:
            fields.append("status=?")
            params.append("pending")

    if not fields:
        return task

    params.extend([plan_id, task_number])
    await db.execute(
        f"UPDATE tasks SET {', '.join(fields)} WHERE plan_id=? AND task_number=?",
        params,
    )
    await db.commit()
    return await get_task(plan_id, task_number)


async def mark_task_complete(plan_id: int, task_number: int, note: str | None = None) -> str:
    task = await get_task(plan_id, task_number)
    if not task:
        return f"Task {task_number} not found."
    await update_task(plan_id, task_number, TaskUpdate(status="completed", notes=note))
    return f"Task {task_number} marked complete: {task['title']}"


async def skip_task(plan_id: int, task_number: int, reason: str | None = None) -> str:
    task = await get_task(plan_id, task_number)
    if not task:
        return f"Task {task_number} not found."
    note = f"Skipped: {reason}" if reason else "Skipped"
    await update_task(plan_id, task_number, TaskUpdate(status="skipped", notes=note))
    return f"Task {task_number} skipped: {task['title']}"


async def reschedule_task(plan_id: int, task_number: int, new_date: str, reason: str | None = None) -> str:
    task = await get_task(plan_id, task_number)
    if not task:
        return f"Task {task_number} not found."
    note = f"Rescheduled to {new_date}" + (f": {reason}" if reason else "")
    await update_task(plan_id, task_number, TaskUpdate(scheduled_date=new_date, notes=note))
    return f"Task {task_number} rescheduled to {new_date}: {task['title']}"


async def add_note_to_task(plan_id: int, task_number: int, note: str) -> str:
    task = await get_task(plan_id, task_number)
    if not task:
        return f"Task {task_number} not found."
    await update_task(plan_id, task_number, TaskUpdate(notes=note))
    return f"Note added to task {task_number}: {task['title']}"


async def get_plan_overview(plan_id: int) -> str:
    """Single efficient aggregation query for plan statistics."""
    db = await get_db()
    tz = ZoneInfo(settings.timezone)
    today = datetime.now(tz).strftime("%Y-%m-%d")

    row = await db.execute_fetchall(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END) as skipped,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='pending' AND scheduled_date < ? THEN 1 ELSE 0 END) as overdue
        FROM tasks WHERE plan_id=?
        """,
        (today, plan_id),
    )
    stats = dict(row[0]) if row else {}

    # Get plan name
    plan_row = await db.execute_fetchall("SELECT name FROM plans WHERE id=?", (plan_id,))
    plan_name = plan_row[0]["name"] if plan_row else "Unknown Plan"

    # Get current active phase
    phases = await db.execute_fetchall(
        "SELECT * FROM phases WHERE plan_id=? AND status='active' LIMIT 1", (plan_id,)
    )
    phase_info = (
        f"Current phase: {phases[0]['phase_number']} - {phases[0]['name']}"
        if phases
        else "No active phase"
    )

    return (
        f"{plan_name} Overview\n"
        f"{phase_info}\n"
        f"Total: {stats.get('total', 0)} | Done: {stats.get('completed', 0)} | "
        f"Skipped: {stats.get('skipped', 0)} | Pending: {stats.get('pending', 0)}\n"
        f"Overdue: {stats.get('overdue', 0)}"
    )


async def get_phases(plan_id: int) -> list[dict]:
    db = await get_db()
    rows = await db.execute_fetchall(
        "SELECT * FROM phases WHERE plan_id=? ORDER BY phase_number", (plan_id,)
    )
    return [dict(r) for r in rows]


async def get_plan_stats(plan_id: int) -> dict:
    """Single efficient query for plan statistics."""
    db = await get_db()
    row = await db.execute_fetchall(
        """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
            SUM(CASE WHEN status='skipped' THEN 1 ELSE 0 END) as skipped,
            SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) as pending,
            SUM(CASE WHEN status='in_progress' THEN 1 ELSE 0 END) as in_progress
        FROM tasks WHERE plan_id=?
        """,
        (plan_id,),
    )
    stats = dict(row[0]) if row else {}

    by_category = await db.execute_fetchall(
        "SELECT category, COUNT(*) as c FROM tasks WHERE plan_id=? GROUP BY category",
        (plan_id,),
    )

    return {
        "total_tasks": stats.get("total", 0),
        "by_status": {
            "completed": stats.get("completed", 0),
            "skipped": stats.get("skipped", 0),
            "pending": stats.get("pending", 0),
            "in_progress": stats.get("in_progress", 0),
        },
        "by_category": {r["category"]: r["c"] for r in by_category},
    }
