from __future__ import annotations

import uuid

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models import Message, Session
from app.schemas import (
    GenerateRequest,
    GenerateResponse,
    MessageIn,
    MessageOut,
    SessionCreateOut,
    SessionOut,
)
from app.agent.pipeline import AgentPipeline

app = FastAPI(title="LocalScript API", version="1.0.0")

pipeline = AgentPipeline()


@app.post("/generate", response_model=GenerateResponse)
async def generate(req: GenerateRequest):
    result = await pipeline.run(req.prompt)
    return GenerateResponse(code=result.code)


@app.post("/chat/sessions", response_model=SessionCreateOut)
async def create_session(db: AsyncSession = Depends(get_db)):
    session = Session()
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return SessionCreateOut(id=session.id)


@app.get("/chat/sessions", response_model=list[SessionOut])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Session).options(selectinload(Session.messages)).order_by(Session.updated_at.desc())
    )
    sessions = result.scalars().all()
    out = []
    for s in sessions:
        last_msg = s.messages[-1].content if s.messages else None
        title = s.title
        if not title and s.messages:
            first_user = next((m for m in s.messages if m.role == "user"), None)
            if first_user:
                title = first_user.content[:60]
        out.append(
            SessionOut(
                id=s.id,
                title=title,
                created_at=s.created_at,
                updated_at=s.updated_at,
                last_message=last_msg[:120] if last_msg else None,
            )
        )
    return out


@app.get("/chat/sessions/{session_id}/messages", response_model=list[MessageOut])
async def get_messages(session_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@app.post("/chat/sessions/{session_id}/messages", response_model=MessageOut)
async def send_message(
    session_id: uuid.UUID, msg: MessageIn, db: AsyncSession = Depends(get_db)
):
    session = await db.get(Session, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    user_msg = Message(session_id=session_id, role="user", content=msg.content)
    db.add(user_msg)
    await db.flush()

    history_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at)
    )
    history = history_result.scalars().all()

    chat_history = [{"role": m.role, "content": m.content} for m in history]

    result = await pipeline.run(msg.content, chat_history=chat_history)

    assistant_msg = Message(
        session_id=session_id,
        role="assistant",
        content=result.full_response,
        lua_code=result.code if result.code else None,
        is_valid=result.is_valid,
    )
    db.add(assistant_msg)

    if not session.title:
        session.title = msg.content[:60]

    await db.commit()
    await db.refresh(assistant_msg)
    return assistant_msg
