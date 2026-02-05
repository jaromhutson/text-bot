from typing import Optional

from pydantic import BaseModel
from enum import Enum


class TaskStatus(str, Enum):
    pending = "pending"
    in_progress = "in_progress"
    completed = "completed"
    skipped = "skipped"
    rescheduled = "rescheduled"


class ExecutionType(str, Enum):
    human = "human"
    agent_assisted = "agent_assisted"


class PhaseStatus(str, Enum):
    upcoming = "upcoming"
    active = "active"
    completed = "completed"


class PlanStatus(str, Enum):
    draft = "draft"
    active = "active"
    completed = "completed"
    archived = "archived"


# --- Plan models ---

class PlanCreate(BaseModel):
    name: str
    type: str = "gtm"
    description: Optional[str] = None


class PlanOut(BaseModel):
    id: int
    name: str
    type: str
    description: Optional[str]
    status: str
    start_date: Optional[str]
    end_date: Optional[str]
    config: Optional[str]
    created_at: str
    updated_at: str


class PlanActivation(BaseModel):
    start_date: str  # YYYY-MM-DD


# --- Phase models ---

class PhaseOut(BaseModel):
    id: int
    plan_id: int
    phase_number: int
    name: str
    description: Optional[str]
    start_date: Optional[str]
    end_date: Optional[str]
    status: str


# --- Task models ---

class TaskOut(BaseModel):
    id: int
    plan_id: int
    task_number: int
    phase_id: Optional[int]
    day_offset: int
    scheduled_date: Optional[str]
    title: str
    description: Optional[str]
    category: str
    execution_type: str
    priority: int
    estimated_minutes: Optional[int]
    status: str
    notes: Optional[str]
    completed_at: Optional[str]


class TaskUpdate(BaseModel):
    status: Optional[TaskStatus] = None
    notes: Optional[str] = None
    scheduled_date: Optional[str] = None
