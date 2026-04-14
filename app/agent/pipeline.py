"""Multi-agent pipeline orchestrator.

Flow:
  User request
    -> Planner (SIMPLE / COMPLEX / QUESTION)
    -> Coder(s)  (single-shot or multi-part + Assembler)
    -> Validator  (syntax)
    -> Test Generator + Executor (Lua asserts)
    -> Judge      (PASS / FAIL)
    -> Fix loop   (up to MAX_FIX_ITERATIONS retries)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass

from app.config import settings
from app.agent.agents.base import shared_llm_call, LLMCallFn
from app.agent.agents.planner import PlannerAgent
from app.agent.agents.coder import CoderAgent
from app.agent.agents.assembler import AssemblerAgent
from app.agent.agents.test_generator import TestGeneratorAgent
from app.agent.agents.judge import JudgeAgent
from app.agent.validator import validate_lua
from app.agent.executor import extract_json_context, run_lua_with_tests
from app.agent.context_manager import ContextManager
from app.agent.prompts import SYSTEM_PROMPT
from app.agent.rag import retrieve

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


class AgentPipeline:
    def __init__(self) -> None:
        self._llm_call: LLMCallFn = shared_llm_call
        self.planner = PlannerAgent(llm_call=self._llm_call)
        self.coder = CoderAgent(llm_call=self._llm_call)
        self.assembler = AssemblerAgent(llm_call=self._llm_call)
        self.test_gen = TestGeneratorAgent(llm_call=self._llm_call)
        self.judge = JudgeAgent(llm_call=self._llm_call)
        self.context_manager = ContextManager(llm_call=self._llm_call)

    # ------------------------------------------------------------------
    # Public entry point (kept compatible with main.py and chat API)
    # ------------------------------------------------------------------

    async def run(
        self,
        user_prompt: str,
        chat_history: list[dict] | None = None,
        existing_summary: str | None = None,
        summarized_count: int = 0,
    ) -> PipelineResult:
        # For chat with history, use the legacy single-shot path
        # (multi-agent decomposition is for stateless /generate)
        if chat_history:
            return await self._run_chat(
                user_prompt, chat_history, existing_summary, summarized_count,
            )
        return await self._run_generate(user_prompt)

    # ------------------------------------------------------------------
    # Multi-agent /generate path
    # ------------------------------------------------------------------

    async def _run_generate(self, user_prompt: str) -> PipelineResult:
        json_ctx = extract_json_context(user_prompt)
        json_ctx_str = json.dumps(json_ctx, ensure_ascii=False) if json_ctx else "(no JSON context)"

        # --- 1. Planner ---
        plan = await self.planner.analyze(user_prompt)
        logger.info("Planner decision: %s", plan.complexity)

        if plan.complexity == "QUESTION":
            return PipelineResult(
                code="",
                full_response=plan.question or "",
                is_question=True,
            )

        # --- 2. Coder ---
        if plan.complexity == "COMPLEX" and plan.steps:
            code = await self._generate_complex(user_prompt, plan.steps)
        else:
            code = await self.coder.generate_simple(user_prompt)

        if not code.strip():
            return PipelineResult(code="", full_response="", is_valid=None)

        # --- 3. Validate + Test + Judge loop ---
        best_code = code
        best_valid = None
        total_iterations = 1

        for attempt in range(1 + MAX_FIX_ITERATIONS):
            syntax = await validate_lua(code)
            syntax_str = "PASS" if syntax.is_valid else f"FAIL: {syntax.error}"

            # Run tests
            test_assertions = await self.test_gen.generate_tests(
                user_prompt, code, json_ctx_str,
            )
            exec_result = await run_lua_with_tests(code, json_ctx, test_assertions)
            test_str = "PASS" if exec_result.tests_passed else f"FAIL: {exec_result.error_summary or exec_result.stderr}"

            # Judge
            verdict = await self.judge.evaluate(code, syntax_str, test_str)
            logger.info(
                "Attempt %d: syntax=%s tests=%s judge=%s",
                attempt + 1,
                "PASS" if syntax.is_valid else "FAIL",
                "PASS" if exec_result.tests_passed else "FAIL",
                "PASS" if verdict.passed else "FAIL",
            )

            if syntax.is_valid:
                best_code = code
                best_valid = True

            if verdict.passed:
                return PipelineResult(
                    code=code,
                    full_response=code,
                    is_valid=True,
                    iterations=total_iterations,
                )

            if attempt < MAX_FIX_ITERATIONS:
                total_iterations += 1
                code = await self.coder.fix(
                    user_prompt,
                    code,
                    feedback=verdict.reason + ("\n" + verdict.fix_instruction if verdict.fix_instruction else ""),
                    test_errors=exec_result.error_summary or exec_result.stderr or syntax.error or "",
                )

        return PipelineResult(
            code=best_code,
            full_response=best_code,
            is_valid=best_valid,
            iterations=total_iterations,
        )

    async def _generate_complex(self, user_prompt: str, steps: list[str]) -> str:
        """Multi-part generation: one coder call per step, then assemble."""
        parts: list[str] = []
        accumulated = ""
        for step in steps:
            part = await self.coder.generate_step(
                user_prompt, step, existing_code=accumulated,
            )
            parts.append(part)
            accumulated += "\n" + part

        assembled = await self.assembler.assemble(parts, user_prompt)
        return assembled

    # ------------------------------------------------------------------
    # Chat path (preserves existing behavior with context management)
    # ------------------------------------------------------------------

    async def _run_chat(
        self,
        user_prompt: str,
        chat_history: list[dict],
        existing_summary: str | None,
        summarized_count: int,
    ) -> PipelineResult:
        system_content = self._build_system_prompt(user_prompt)

        updated_summary: str | None = existing_summary
        new_summarized_count = summarized_count

        ctx = await self.context_manager.prepare(
            system_prompt=system_content,
            chat_history=chat_history,
            existing_summary=existing_summary,
            summarized_count=summarized_count,
        )
        messages = ctx.messages
        updated_summary = ctx.summary
        new_summarized_count = ctx.summarized_count

        response_text = await self._llm_call(messages)

        if _is_clarifying_question(response_text):
            return PipelineResult(
                code="",
                full_response=response_text,
                is_valid=None,
                is_question=True,
                iterations=1,
                updated_summary=updated_summary,
                summarized_count=new_summarized_count,
            )

        code = _extract_lua_code(response_text)
        if not code:
            code = _fallback_extract(response_text)
        if not code:
            return PipelineResult(
                code=response_text.strip(),
                full_response=response_text,
                is_valid=None,
                iterations=1,
                updated_summary=updated_summary,
                summarized_count=new_summarized_count,
            )

        code = _clean_code(code)
        validation = await validate_lua(code)
        iterations = 1

        while not validation.is_valid and iterations < MAX_FIX_ITERATIONS + 1:
            iterations += 1
            from app.agent.prompts import FIX_PROMPT_TEMPLATE
            fix_content = FIX_PROMPT_TEMPLATE.format(code=code, error=validation.error)
            messages.append({"role": "assistant", "content": response_text})
            messages.append({"role": "user", "content": fix_content})

            response_text = await self._llm_call(messages)
            new_code = _extract_lua_code(response_text)
            if not new_code:
                new_code = _fallback_extract(response_text)
            if new_code:
                code = _clean_code(new_code)
            validation = await validate_lua(code)

        return PipelineResult(
            code=code,
            full_response=response_text,
            is_valid=validation.is_valid,
            iterations=iterations,
            updated_summary=updated_summary,
            summarized_count=new_summarized_count,
        )

    def _build_system_prompt(self, user_query: str) -> str:
        context_chunks = retrieve(user_query, top_k=3)
        if context_chunks:
            rag_section = "\n=== RELEVANT DOMAIN KNOWLEDGE ===\n" + "\n---\n".join(context_chunks) + "\n"
        else:
            rag_section = ""
        return SYSTEM_PROMPT.format(rag_context=rag_section)


# ------------------------------------------------------------------
# Helpers reused from the original pipeline for the chat path
# ------------------------------------------------------------------

import re  # noqa: E402


def _extract_lua_code(text: str) -> str | None:
    for pat in [r"```lua\s*\n(.*?)```", r"```\s*\n(.*?)```"]:
        m = re.search(pat, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _fallback_extract(text: str) -> str | None:
    lines = text.strip().split("\n")
    code_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("```") or stripped.startswith("---"):
            continue
        if any(stripped.lower().startswith(w) for w in [
            "here", "this", "the ", "note", "below", "above",
            "вот", "этот", "данный", "ниже",
        ]):
            continue
        code_lines.append(line)

    joined = "\n".join(code_lines)
    lua_keywords = ("return", "local", "function", "for ", "if ", "while ", "wf.", "end", "table.", "string.", "_utils")
    if code_lines and any(kw in joined for kw in lua_keywords):
        return joined
    return None


def _clean_code(code: str) -> str:
    code = code.strip()
    m = re.match(r'^lua\s*\{(.*)\}\s*lua$', code, re.DOTALL)
    if m:
        code = m.group(1).strip()
    if (code.startswith('"') and code.endswith('"')) or (code.startswith("'") and code.endswith("'")):
        code = code[1:-1]
    code = re.sub(r'\bprint\((.+?)\)\s*$', r'return \1', code)
    return code


def _is_clarifying_question(text: str) -> bool:
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
