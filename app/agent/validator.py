import asyncio
from dataclasses import dataclass


@dataclass
class ValidationResult:
    is_valid: bool
    error: str | None = None


async def validate_lua(code: str) -> ValidationResult:
    try:
        proc = await asyncio.create_subprocess_exec(
            "lua5.4", "-p", "-",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await asyncio.wait_for(proc.communicate(input=code.encode()), timeout=5.0)
        if proc.returncode == 0:
            return ValidationResult(is_valid=True)
        return ValidationResult(is_valid=False, error=stderr.decode().strip())
    except FileNotFoundError:
        return ValidationResult(is_valid=True, error=None)
    except asyncio.TimeoutError:
        return ValidationResult(is_valid=False, error="Lua syntax check timed out")
