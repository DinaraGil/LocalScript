"""Base agent with shared LLM call logic."""

from __future__ import annotations

import logging
from typing import Callable, Awaitable

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

LLMCallFn = Callable[[list[dict]], Awaitable[str]]


async def shared_llm_call(messages: list[dict]) -> str:
    """Single shared LLM call function used by all agents."""
    url = f"{settings.ollama_base_url}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_ctx": settings.ollama_num_ctx,
            "num_predict": settings.ollama_num_predict,
            "temperature": 0.1,
            "top_p": 0.9,
            "repeat_penalty": 1.1,
        },
    }
    async with httpx.AsyncClient(timeout=300.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["message"]["content"]


class BaseAgent:
    """Base class for all pipeline agents."""

    def __init__(
        self,
        system_prompt: str,
        llm_call: LLMCallFn | None = None,
    ) -> None:
        self.system_prompt = system_prompt
        self._llm_call = llm_call or shared_llm_call

    async def call(self, user_content: str) -> str:
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": user_content},
        ]
        return await self._llm_call(messages)

    async def call_with_history(self, messages: list[dict]) -> str:
        full = [{"role": "system", "content": self.system_prompt}] + messages
        return await self._llm_call(full)
