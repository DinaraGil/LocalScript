import asyncio
import shutil
from dataclasses import dataclass


LUA_STUB_PREAMBLE = """\
local _mt = {__index = function(t, k) return setmetatable({}, getmetatable(t)) end, __newindex = function() end, __call = function() return setmetatable({}, {__index = function(t,k) return t end}) end}
wf = setmetatable({}, _mt)
wf.vars = setmetatable({}, _mt)
wf.initVariables = setmetatable({}, _mt)
_utils = setmetatable({}, _mt)
"""

PREAMBLE_LINES = LUA_STUB_PREAMBLE.count("\n")


def _find_lua_checker() -> list[str] | None:
    for cmd in (["luac", "-p", "-"], ["lua5.4", "-p", "-"], ["lua", "-p", "-"]):
        if shutil.which(cmd[0]):
            return cmd
    return None


@dataclass
class ValidationResult:
    is_valid: bool
    error: str | None = None


def _adjust_error(error_text: str) -> str:
    lines = error_text.split("\n")
    adjusted = []
    for line in lines:
        clean = line.replace("stdin:", "").replace("luac:", "").strip()
        if not clean:
            continue
        try:
            parts = clean.split(":", 1)
            lineno = int(parts[0].strip())
            adjusted_lineno = lineno - PREAMBLE_LINES
            if adjusted_lineno < 1:
                adjusted_lineno = 1
            adjusted.append(f"line {adjusted_lineno}:{parts[1]}")
        except (ValueError, IndexError):
            adjusted.append(line.strip())
    return "\n".join(adjusted) if adjusted else error_text


async def validate_lua(code: str) -> ValidationResult:
    checker = _find_lua_checker()
    if not checker:
        return ValidationResult(is_valid=True, error=None)

    wrapped = LUA_STUB_PREAMBLE + code
    try:
        proc = await asyncio.create_subprocess_exec(
            *checker,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(input=wrapped.encode()), timeout=5.0)
        if proc.returncode == 0:
            return ValidationResult(is_valid=True)
        return ValidationResult(is_valid=False, error=_adjust_error(stderr.decode()))
    except asyncio.TimeoutError:
        return ValidationResult(is_valid=False, error="Lua syntax check timed out")
