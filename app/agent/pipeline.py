from __future__ import annotations

import re
import logging
from dataclasses import dataclass, field

import httpx

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT, FIX_PROMPT_TEMPLATE
from app.agent.validator import validate_lua
from app.agent.rag import retrieve

logger = logging.getLogger(__name__)

MAX_FIX_ITERATIONS = 2


@dataclass
class PipelineResult:
    code: str
    full_response: str
    is_valid: bool | None = None
    iterations: int = 1


def extract_lua_code(text: str) -> str | None:
    patterns = [
        r"```lua\s*\n(.*?)```",
        r"```\s*\n(.*?)```",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return m.group(1).strip()

    lines = text.strip().split("\n")
    code_lines = [
        l for l in lines
        if not l.startswith("#") and not l.startswith("//") and l.strip()
    ]
    if code_lines and any(kw in "\n".join(code_lines) for kw in ("function", "return", "local", "for ", "if ", "wf.")):
        return "\n".join(code_lines)
    return None


def is_clarifying_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    code = extract_lua_code(text)
    if code:
        return False
    return stripped.endswith("?") or any(
        kw in stripped.lower() for kw in ["уточни", "clarify", "could you", "можете", "какой", "какие", "что именно", "what exactly"]
    )


class AgentPipeline:
    def __init__(self) -> None:
        self.ollama_url = f"{settings.ollama_base_url}/api/chat"
        self.model = settings.ollama_model

    async def _llm_call(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": 4096,
                "num_predict": 256,
            },
        }
        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(self.ollama_url, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return data["message"]["content"]

    def _build_system_prompt(self, user_query: str) -> str:
        context_chunks = retrieve(user_query, top_k=3)
        if context_chunks:
            rag_section = "\nRELEVANT EXAMPLES:\n" + "\n---\n".join(context_chunks) + "\n"
        else:
            rag_section = ""
        return SYSTEM_PROMPT.format(rag_context=rag_section)

    async def run(
        self,
        user_prompt: str,
        chat_history: list[dict] | None = None,
    ) -> PipelineResult:
        system_content = self._build_system_prompt(user_prompt)
        messages: list[dict] = [{"role": "system", "content": system_content}]

        if chat_history:
            messages.extend(chat_history)
        else:
            messages.append({"role": "user", "content": user_prompt})

        response_text = await self._llm_call(messages)

        if is_clarifying_question(response_text):
            return PipelineResult(
                code="",
                full_response=response_text,
                is_valid=None,
                iterations=1,
            )

        code = extract_lua_code(response_text)
        if not code:
            return PipelineResult(
                code=response_text.strip(),
                full_response=response_text,
                is_valid=None,
                iterations=1,
            )

        validation = await validate_lua(code)
        iterations = 1

        while not validation.is_valid and iterations < MAX_FIX_ITERATIONS + 1:
            iterations += 1
            fix_content = FIX_PROMPT_TEMPLATE.format(code=code, error=validation.error)
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": fix_content})

            response_text = await self._llm_call(messages)
            new_code = extract_lua_code(response_text)
            if new_code:
                code = new_code
            validation = await validate_lua(code)

        return PipelineResult(
            code=code,
            full_response=response_text,
            is_valid=validation.is_valid,
            iterations=iterations,
        )
