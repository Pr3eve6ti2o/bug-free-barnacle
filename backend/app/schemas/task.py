from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TaskBase(BaseModel):
    title: str
    description: str
    condition_value: int
    reward: int
    type: str
    condition_type: str
    reward_type: str = "token"
    multiplier_pct: float = 0
    link_url: Optional[str] = None


class TaskCreate(TaskBase):
    pass


class TaskRead(TaskBase):
    id: int

    class Config:
        from_attributes = True


class UserTaskRead(BaseModel):
    id: int
    task: TaskRead
    progress: int
    is_completed: bool
    is_claimed: bool = False

    class Config:
        from_attributes = True


class TaskClaimResponse(BaseModel):
    success: bool
    reward: Optional[int] = None
    new_balance: Optional[int] = None
    task_id: Optional[int] = None
    error: Optional[str] = None
    reward_type: Optional[str] = None
    multiplier_pct: Optional[float] = None
    task_boost_pct: Optional[float] = None