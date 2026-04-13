from __future__ import annotations

import re
import logging
from dataclasses import dataclass

import httpx

from app.config import settings
from app.agent.prompts import SYSTEM_PROMPT, FIX_PROMPT_TEMPLATE
from app.agent.validator import validate_lua
from app.agent.rag import retrieve
from app.agent.context_manager import ContextManager

logger = logging.getLogger(__name__)

MAX_FIX_ITERATIONS = 2


@dataclass
class PipelineResult:
    code: str
    full_response: str
    is_valid: bool | None = None
    is_question: bool = False
    iterations: int = 1
    updated_summary: str | None = None
    summarized_count: int = 0


def extract_lua_code(text: str) -> str | None:
    patterns = [
        r"```lua\s*\n(.*?)```",
        r"```\s*\n(.*?)```",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def clean_code(code: str) -> str:
    code = code.strip()
    # strip lua{...}lua wrapper if model included it
    m = re.match(r'^lua\s*\{(.*)\}\s*lua$', code, re.DOTALL)
    if m:
        code = m.group(1).strip()
    # strip surrounding quotes
    if (code.startswith('"') and code.endswith('"')) or (code.startswith("'") and code.endswith("'")):
        code = code[1:-1]
    # remove print() wrappers — replace print(X) at end with return X
    code = re.sub(r'\bprint\((.+?)\)\s*$', r'return \1', code)
    return code


def fallback_extract(text: str) -> str | None:
    lines = text.strip().split("\n")
    code_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("```") or stripped.startswith("---"):
            continue
        if any(stripped.lower().startswith(w) for w in [
            "here", "this", "the ", "note", "below", "above", "вот", "этот", "данный", "ниже",
        ]):
            continue
        code_lines.append(line)

    joined = "\n".join(code_lines)
    lua_keywords = ("return", "local", "function", "for ", "if ", "while ", "wf.", "end", "table.", "string.", "_utils")
    if code_lines and any(kw in joined for kw in lua_keywords):
        return joined
    return None


def is_clarifying_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    if "```" in stripped:
        return False
    lua_keywords = ("return ", "local ", "function ", "wf.", "for ", "if ", "table.", "_utils")
    if any(kw in stripped for kw in lua_keywords):
        return False
    if stripped.endswith("?"):
        return True
    question_markers = [
        "уточни", "clarify", "could you", "можете", "какой", "какие",
        "что именно", "what exactly", "какую", "какое", "укажите",
        "please specify", "which ", "что вы имеете",
    ]
    return any(kw in stripped.lower() for kw in question_markers)


class AgentPipeline:
    def __init__(self) -> None:
        self.ollama_url = f"{settings.ollama_base_url}/api/chat"
        self.model = settings.ollama_model
        self.context_manager = ContextManager(llm_call=self._llm_call)

    async def _llm_call(self, messages: list[dict]) -> str:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_ctx": settings.ollama_num_ctx,
                "num_predict": settings.ollama_num_predict,
                "temperature": 0.1, #prob need to change
                "top_p": 0.9,
                "repeat_penalty": 1.1,
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
            rag_section = "\n=== RELEVANT DOMAIN KNOWLEDGE ===\n" + "\n---\n".join(context_chunks) + "\n"
        else:
            rag_section = ""
        return SYSTEM_PROMPT.format(rag_context=rag_section)

    async def run(
        self,
        user_prompt: str,
        chat_history: list[dict] | None = None,
        existing_summary: str | None = None,
        summarized_count: int = 0,
    ) -> PipelineResult:
        system_content = self._build_system_prompt(user_prompt)

        updated_summary: str | None = existing_summary
        new_summarized_count = summarized_count

        if chat_history:
            ctx = await self.context_manager.prepare(
                system_prompt=system_content,
                chat_history=chat_history,
                existing_summary=existing_summary,
                summarized_count=summarized_count,
            )
            messages = ctx.messages
            updated_summary = ctx.summary
            new_summarized_count = ctx.summarized_count
        else:
            messages = [
                {"role": "system", "content": system_content},
                {"role": "user", "content": user_prompt},
            ]

        response_text = await self._llm_call(messages)

        if is_clarifying_question(response_text):
            return PipelineResult(
                code="",
                full_response=response_text,
                is_valid=None,
                is_question=True,
                iterations=1,
                updated_summary=updated_summary,
                summarized_count=new_summarized_count,
            )

        code = extract_lua_code(response_text)
        if not code:
            code = fallback_extract(response_text)
        if not code:
            return PipelineResult(
                code=response_text.strip(),
                full_response=response_text,
                is_valid=None,
                iterations=1,
                updated_summary=updated_summary,
                summarized_count=new_summarized_count,
            )

        code = clean_code(code)

        validation = await validate_lua(code)
        iterations = 1

        while not validation.is_valid and iterations < MAX_FIX_ITERATIONS + 1:
            iterations += 1
            fix_content = FIX_PROMPT_TEMPLATE.format(code=code, error=validation.error)
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": fix_content})

            response_text = await self._llm_call(messages)
            new_code = extract_lua_code(response_text)
            if not new_code:
                new_code = fallback_extract(response_text)
            if new_code:
                code = clean_code(new_code)
            validation = await validate_lua(code)

        return PipelineResult(
            code=code,
            full_response=response_text,
            is_valid=validation.is_valid,
            iterations=iterations,
            updated_summary=updated_summary,
            summarized_count=new_summarized_count,
        )
