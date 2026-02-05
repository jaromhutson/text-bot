from __future__ import annotations

import asyncio

import aiosqlite

from app.config import settings

_db: aiosqlite.Connection | None = None
_lock = asyncio.Lock()


async def get_db() -> aiosqlite.Connection:
    global _db
    async with _lock:
        if _db is None:
            _db = await aiosqlite.connect(settings.database_url)
            _db.row_factory = aiosqlite.Row
            await _db.execute("PRAGMA journal_mode=WAL")
            await _db.execute("PRAGMA foreign_keys=ON")
    return _db


async def close_db() -> None:
    global _db
    async with _lock:
        if _db:
            await _db.close()
            _db = None


async def init_db() -> None:
    db = await get_db()
    await db.executescript("""
        CREATE TABLE IF NOT EXISTS plans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'gtm',
            description TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            start_date TEXT,
            end_date TEXT,
            config TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS phases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            phase_number INTEGER NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            start_date TEXT,
            end_date TEXT,
            status TEXT NOT NULL DEFAULT 'upcoming',
            UNIQUE(plan_id, phase_number)
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER NOT NULL REFERENCES plans(id) ON DELETE CASCADE,
            phase_id INTEGER REFERENCES phases(id) ON DELETE SET NULL,
            task_number INTEGER NOT NULL,
            day_offset INTEGER NOT NULL CHECK(day_offset >= 0),
            scheduled_date TEXT,
            title TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL DEFAULT 'general',
            execution_type TEXT NOT NULL DEFAULT 'human',
            priority INTEGER NOT NULL DEFAULT 2 CHECK(priority BETWEEN 1 AND 3),
            estimated_minutes INTEGER DEFAULT 15 CHECK(estimated_minutes >= 0),
            status TEXT NOT NULL DEFAULT 'pending',
            notes TEXT,
            completed_at TEXT,
            UNIQUE(plan_id, task_number)
        );

        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            plan_id INTEGER REFERENCES plans(id),
            direction TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'sms',
            phone_number TEXT,
            content TEXT NOT NULL,
            twilio_sid TEXT UNIQUE,
            ai_interpretation TEXT,
            ai_actions_taken TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS bot_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE UNIQUE INDEX IF NOT EXISTS idx_tasks_plan_number
            ON tasks(plan_id, task_number);
        CREATE INDEX IF NOT EXISTS idx_tasks_date
            ON tasks(scheduled_date);
        CREATE INDEX IF NOT EXISTS idx_tasks_date_status
            ON tasks(scheduled_date, status);
        CREATE INDEX IF NOT EXISTS idx_tasks_plan_status
            ON tasks(plan_id, status);
        CREATE INDEX IF NOT EXISTS idx_phases_plan
            ON phases(plan_id);
        CREATE INDEX IF NOT EXISTS idx_conversations_created
            ON conversations(created_at);
        CREATE INDEX IF NOT EXISTS idx_conversations_sid
            ON conversations(twilio_sid);
    """)
    await db.commit()
