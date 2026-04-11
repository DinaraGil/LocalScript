from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    prompt: str


class GenerateResponse(BaseModel):
    code: str


class SessionOut(BaseModel):
    id: uuid.UUID
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_message: str | None = None

    model_config = {"from_attributes": True}


class MessageIn(BaseModel):
    content: str


class MessageOut(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    role: str
    content: str
    lua_code: str | None
    is_valid: bool | None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionCreateOut(BaseModel):
    id: uuid.UUID
