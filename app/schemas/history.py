from datetime import datetime

from pydantic import BaseModel, ConfigDict


class RevisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entity_type: str
    entity_id: str
    entity_name: str | None = None
    contributor: str | None
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    reason: str
    created_at: datetime
