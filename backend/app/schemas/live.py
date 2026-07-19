from typing import Any

from pydantic import BaseModel, Field


class LiveSnapshotIn(BaseModel):
    seq: int = Field(ge=0)
    game_time_s: float = Field(ge=0)
    payload: dict[str, Any] | None = None


class LiveSnapshotBatchRequest(BaseModel):
    riot_id: str = Field(min_length=3, max_length=96)
    collector_version: str | None = Field(default=None, max_length=32)
    snapshots: list[LiveSnapshotIn] = Field(max_length=500)


class LiveCompleteRequest(BaseModel):
    riot_id: str = Field(min_length=3, max_length=96)
    game_start_ms: int | None = Field(default=None, ge=0)
    collector_version: str | None = Field(default=None, max_length=32)


class LiveSnapshotBatchResponse(BaseModel):
    session_id: str
    received: int
    accepted: int


class LiveSessionResponse(BaseModel):
    session_id: str
    riot_id: str
    state: str
    game_start_ms: int | None
    matched_match_id: str | None
    collector_version: str | None
    schema_version: int
