from __future__ import annotations

import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Header

from app.config import settings
from app.models import PlanActivation, PlanCreate, TaskUpdate
from app.services.plans import (
    activate_plan,
    archive_plan,
    complete_plan,
    create_plan,
    get_plan,
    list_plans,
)
from app.services.tasks import (
    get_tasks_for_date,
    get_task,
    update_task,
    get_phases,
    get_plan_stats,
)
from app.services.sms import send_daily_tasks, send_weekly_review

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin", tags=["admin"])

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def verify_bearer_token(authorization: str = Header(...)) -> None:
    """Validate Authorization: Bearer <token> header."""
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")
    token = authorization[7:]
    if token != settings.admin_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


# --- Plan endpoints ---

@router.post("/plans", dependencies=[Depends(verify_bearer_token)])
async def create_new_plan(body: PlanCreate):
    plan = await create_plan(body.name, body.type, body.description)
    return plan


@router.get("/plans", dependencies=[Depends(verify_bearer_token)])
async def list_all_plans(status: Optional[str] = None):
    return {"plans": await list_plans(status)}


@router.get("/plans/{plan_id}", dependencies=[Depends(verify_bearer_token)])
async def get_single_plan(plan_id: int):
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/plans/{plan_id}/activate", dependencies=[Depends(verify_bearer_token)])
async def activate(plan_id: int, body: PlanActivation):
    if not DATE_RE.match(body.start_date):
        raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")
    plan = await get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    count = await activate_plan(plan_id, body.start_date)
    return {"status": "activated", "tasks_scheduled": count}


@router.post("/plans/{plan_id}/complete", dependencies=[Depends(verify_bearer_token)])
async def complete(plan_id: int):
    plan = await complete_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/plans/{plan_id}/archive", dependencies=[Depends(verify_bearer_token)])
async def archive(plan_id: int):
    plan = await archive_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


# --- Plan-scoped task endpoints ---

@router.get("/plans/{plan_id}/tasks", dependencies=[Depends(verify_bearer_token)])
async def list_plan_tasks(plan_id: int, date: Optional[str] = None, status: Optional[str] = None):
    if date and not DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    tasks = await get_tasks_for_date(plan_id, date, status=status)
    return {"tasks": tasks}


@router.get("/plans/{plan_id}/tasks/{task_number}", dependencies=[Depends(verify_bearer_token)])
async def get_plan_task(plan_id: int, task_number: int):
    task = await get_task(plan_id, task_number)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/plans/{plan_id}/tasks/{task_number}", dependencies=[Depends(verify_bearer_token)])
async def patch_plan_task(plan_id: int, task_number: int, body: TaskUpdate):
    task = await update_task(plan_id, task_number, body)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/plans/{plan_id}/phases", dependencies=[Depends(verify_bearer_token)])
async def list_plan_phases(plan_id: int):
    return {"phases": await get_phases(plan_id)}


@router.get("/plans/{plan_id}/stats", dependencies=[Depends(verify_bearer_token)])
async def plan_stats(plan_id: int):
    return await get_plan_stats(plan_id)


@router.post("/plans/{plan_id}/send-now", dependencies=[Depends(verify_bearer_token)])
async def send_now_plan(plan_id: int, date: Optional[str] = None):
    if date and not DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    result = await send_daily_tasks(plan_id, date)
    return {"status": "sent", "detail": result}


@router.post("/plans/{plan_id}/send-review", dependencies=[Depends(verify_bearer_token)])
async def send_review_plan(plan_id: int):
    result = await send_weekly_review(plan_id)
    return {"status": "sent", "detail": result}


# --- Backward-compat flat routes (use default plan) ---

@router.post("/activate", dependencies=[Depends(verify_bearer_token)])
async def activate_default(body: PlanActivation):
    if not DATE_RE.match(body.start_date):
        raise HTTPException(status_code=400, detail="start_date must be YYYY-MM-DD")
    count = await activate_plan(settings.default_plan_id, body.start_date)
    return {"status": "activated", "tasks_scheduled": count}


@router.get("/tasks", dependencies=[Depends(verify_bearer_token)])
async def list_tasks(date: Optional[str] = None, status: Optional[str] = None):
    if date and not DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    tasks = await get_tasks_for_date(settings.default_plan_id, date, status=status)
    return {"tasks": tasks}


@router.get("/tasks/{task_number}", dependencies=[Depends(verify_bearer_token)])
async def get_single_task(task_number: int):
    task = await get_task(settings.default_plan_id, task_number)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.patch("/tasks/{task_number}", dependencies=[Depends(verify_bearer_token)])
async def patch_task(task_number: int, body: TaskUpdate):
    task = await update_task(settings.default_plan_id, task_number, body)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/phases", dependencies=[Depends(verify_bearer_token)])
async def list_phases_default():
    return {"phases": await get_phases(settings.default_plan_id)}


@router.get("/stats", dependencies=[Depends(verify_bearer_token)])
async def stats_default():
    return await get_plan_stats(settings.default_plan_id)


@router.post("/send-now", dependencies=[Depends(verify_bearer_token)])
async def send_now(date: Optional[str] = None):
    if date and not DATE_RE.match(date):
        raise HTTPException(status_code=400, detail="date must be YYYY-MM-DD")
    result = await send_daily_tasks(settings.default_plan_id, date)
    return {"status": "sent", "detail": result}
