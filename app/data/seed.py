import logging

from app.database import get_db
from app.data.gtm_plan import GTM_PHASES, GTM_TASKS

logger = logging.getLogger(__name__)


async def seed_if_empty() -> None:
    """Seed the database with the GTM plan if no plans exist (idempotent)."""
    db = await get_db()
    rows = await db.execute_fetchall("SELECT COUNT(*) as c FROM plans")
    if rows[0]["c"] > 0:
        logger.info("Database already seeded — skipping")
        return
    await seed_gtm_plan()


async def seed_gtm_plan() -> None:
    """Create the Tidbit GTM plan with all phases and tasks."""
    db = await get_db()

    # Check if the GTM plan already exists
    existing = await db.execute_fetchall("SELECT id FROM plans WHERE name='Tidbit GTM Plan'")
    if existing:
        logger.info("GTM plan already exists (id=%d) — skipping seed", existing[0]["id"])
        return

    # Create the plan
    cursor = await db.execute(
        "INSERT INTO plans (name, type, description) VALUES (?, ?, ?)",
        ("Tidbit GTM Plan", "gtm", "8-week go-to-market launch plan for Tidbit"),
    )
    plan_id = cursor.lastrowid

    # Create phases
    phase_id_map = {}  # phase_number -> db id
    for phase in GTM_PHASES:
        cursor = await db.execute(
            "INSERT INTO phases (plan_id, phase_number, name, description) VALUES (?, ?, ?, ?)",
            (plan_id, phase["phase_number"], phase["name"], phase["description"]),
        )
        phase_id_map[phase["phase_number"]] = cursor.lastrowid

    # Create tasks
    for task in GTM_TASKS:
        phase_id = phase_id_map.get(task["phase_number"])
        await db.execute(
            """INSERT INTO tasks
               (plan_id, phase_id, task_number, day_offset, title, description,
                category, execution_type, priority, estimated_minutes)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                plan_id,
                phase_id,
                task["task_number"],
                task["day_offset"],
                task["title"],
                task["description"],
                task["category"],
                task["execution_type"],
                task["priority"],
                task["estimated_minutes"],
            ),
        )

    await db.commit()
    logger.info("Seeded GTM plan (id=%d) with %d phases and %d tasks", plan_id, len(GTM_PHASES), len(GTM_TASKS))
