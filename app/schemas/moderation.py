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
    votes_for: int = 0
    votes_against: int = 0
    my_vote: int = 0  # +1, -1 ou 0 (nao votou)
    vote_threshold: int = 0


class ModerationDecision(BaseModel):
    note: str | None = None


class VoteRequest(BaseModel):
    value: int  # +1 a favor, -1 contra, 0 retira o voto
