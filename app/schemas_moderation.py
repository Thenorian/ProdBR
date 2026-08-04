from datetime import datetime

from pydantic import BaseModel


class PendingChangeOut(BaseModel):
    id: int
    entity_type: str
    entity_id: str | None
    payload: dict
    reason: str
    contributor: str
    status: str
    created_at: datetime


class ModerationDecision(BaseModel):
    note: str | None = None
