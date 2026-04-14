"""Coder agent: generates Lua code (single-shot or multi-part)."""

from __future__ import annotations

import re
import logging

from app.agent.agents.base import BaseAgent, LLMCallFn
from app.agent.prompts import CODER_PROMPT, CODER_STEP_PROMPT
from app.agent.rag import retrieve

logger = logging.getLogger(__name__)


def _extract_lua(text: str) -> str | None:
    for pat in [r"```lua\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _fallback_extract(text: str) -> str:
    """Extract code-like lines when no fenced block is found."""
    lines = []
    for line in text.strip().splitlines():
        s = line.strip()
        if not s or s.startswith("```") or s.startswith("---"):
            continue
        if any(s.lower().startswith(w) for w in [
            "here", "this", "the ", "note", "below", "above",
            "вот", "этот", "данный", "ниже",
        ]):
            continue
        lines.append(line)
    return "\n".join(lines)


def _clean_code(code: str) -> str:
    code = code.strip()
    m = re.match(r'^lua\s*\{(.*)\}\s*lua$', code, re.DOTALL)
    if m:
        code = m.group(1).strip()
    if (code.startswith('"') and code.endswith('"')) or (code.startswith("'") and code.endswith("'")):
        code = code[1:-1]
    code = re.sub(r'\bprint\((.+?)\)\s*$', r'return \1', code)
    return code


def _build_rag_context(user_query: str) -> str:
    chunks = retrieve(user_query, top_k=3)
    if chunks:
        return "\n=== RELEVANT DOMAIN KNOWLEDGE ===\n" + "\n---\n".join(chunks) + "\n"
    return ""


class CoderAgent(BaseAgent):
    def __init__(self, llm_call: LLMCallFn | None = None) -> None:
        super().__init__(system_prompt="", llm_call=llm_call)

    async def generate_simple(self, user_prompt: str) -> str:
        """Single-shot generation for simple tasks."""
        rag = _build_rag_context(user_prompt)
        prompt = CODER_PROMPT.format(rag_context=rag)
        self.system_prompt = prompt
        response = await self.call(user_prompt)
        return self._extract_and_clean(response)

    async def generate_step(
        self,
        user_prompt: str,
        step_description: str,
        existing_code: str = "",
    ) -> str:
        """Generate code for one step of a complex task."""
        rag = _build_rag_context(user_prompt)
        prompt = CODER_STEP_PROMPT.format(
            rag_context=rag,
            existing_code=existing_code or "(none yet)",
            step_description=step_description,
        )
        self.system_prompt = prompt
        response = await self.call(user_prompt)
        return self._extract_and_clean(response)

    async def fix(self, user_prompt: str, code: str, feedback: str, test_errors: str) -> str:
        """Fix code based on judge feedback."""
        from app.agent.prompts import FIX_WITH_FEEDBACK_TEMPLATE
        rag = _build_rag_context(user_prompt)
        self.system_prompt = CODER_PROMPT.format(rag_context=rag)
        fix_request = FIX_WITH_FEEDBACK_TEMPLATE.format(
            task=user_prompt,
            code=code,
            feedback=feedback,
            test_errors=test_errors,
        )
        response = await self.call(fix_request)
        return self._extract_and_clean(response)

    @staticmethod
    def _extract_and_clean(response: str) -> str:
        code = _extract_lua(response)
        if not code:
            code = _fallback_extract(response)
        return _clean_code(code) if code else response.strip()
