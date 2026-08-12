"""
Secure Python sandbox for code_snippet skills via RestrictedPython.

PR-21: SafeExecutor compiles and runs user/LLM-written Python expressions
and functions in a RestrictedPython sandbox — no I/O, no imports, no subprocess.
"""
import asyncio
import ctypes
import io
import logging
import math
import re as _re_module
import statistics as _statistics_module
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as _Decimal

from RestrictedPython import compile_restricted, limited_builtins
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safer_getattr,
)
from RestrictedPython.PrintCollector import PrintCollector

logger = logging.getLogger("pulse.skills.sandbox")


# ═══════════════════════════════════════════════════════════════════════════════
# Sandbox errors
# ═══════════════════════════════════════════════════════════════════════════════

class SandboxError(Exception):
    """Base error for sandbox execution failures."""


class SandboxTimeout(SandboxError):
    """Execution exceeded the configured timeout."""


class SandboxSecurityViolation(SandboxError):
    """Code attempted a forbidden operation (import, open, etc.)."""


# ═══════════════════════════════════════════════════════════════════════════════
# Safe builtins — RestrictedPython's limited_builtins + extras
# ═══════════════════════════════════════════════════════════════════════════════

_SAFE_BUILTINS: dict = {
    **limited_builtins,
    "True": True,
    "False": False,
    "None": None,
    "abs": abs,
    "all": all,
    "any": any,
    "bin": bin,
    "bool": bool,
    "bytes": bytes,
    "chr": chr,
    "complex": complex,
    "dict": dict,
    "divmod": divmod,
    "enumerate": enumerate,
    "filter": filter,
    "float": float,
    "format": format,
    "frozenset": frozenset,
    "hash": hash,
    "hex": hex,
    "int": int,
    "isinstance": isinstance,
    "issubclass": issubclass,
    "iter": iter,
    "len": len,
    "list": list,
    "map": map,
    "max": max,
    "min": min,
    "next": next,
    "oct": oct,
    "ord": ord,
    "pow": pow,
    "range": range,
    "repr": repr,
    "reversed": reversed,
    "round": round,
    "set": set,
    "slice": slice,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "type": type,
    "zip": zip,
    # RestrictedPython's native print collector (exec mode injects
    # _print = _print_(_getattr_) at the top of the module).
    "_print_": PrintCollector,
}


# ═══════════════════════════════════════════════════════════════════════════════
# Safe modules — whitelisted imports
# ═══════════════════════════════════════════════════════════════════════════════

_SAFE_MODULES: dict[str, object] = {
    "json": None,       # lazy import below
    "math": math,
    "datetime": None,   # lazy import below
    "statistics": _statistics_module,
    "re": _re_module,
    "decimal": None,    # lazy import below
}


def _get_safe_module(name: str) -> object:
    """Lazy-import a whitelisted module."""
    if name == "json":
        import json as _json

        return _json
    if name == "datetime":
        import datetime as _datetime

        return _datetime
    if name == "decimal":
        return __import__("decimal")
    return None


def _build_safe_globals() -> dict:
    """Build the globals dict for a sandbox execution.

    Includes safe builtins and whitelisted module references.
    """
    safe_globals: dict = {
        "__builtins__": _SAFE_BUILTINS,
        "__name__": "sandbox",
        "__doc__": None,
        # Guards required by RestrictedPython compiled code
        "_getattr_": safer_getattr,
        "_getitem_": lambda obj, key: obj[key],
        "_write_": full_write_guard,
        "_getiter_": iter,
        "_iter_unpack_sequence_": guarded_iter_unpack_sequence,
        "_unpack_sequence_": guarded_unpack_sequence,
    }

    # Inject whitelisted modules by their short name
    for name in _SAFE_MODULES:
        safe_globals[name] = _get_safe_module(name) if _SAFE_MODULES[name] is None else _SAFE_MODULES[name]

    return safe_globals


# ═══════════════════════════════════════════════════════════════════════════════
# SafeExecutor
# ═══════════════════════════════════════════════════════════════════════════════

class SafeExecutor:
    """Compile and execute Python code in a RestrictedPython sandbox.

    Usage:
        executor = SafeExecutor()
        result = await executor.execute("2 + 3", {}, timeout_ms=5000)
        result = await executor.execute("def main(x, y): return x * y", {"x": 4, "y": 7})
    """

    def __init__(self):
        self._safe_globals = _build_safe_globals()

    @staticmethod
    def _terminate_sandbox_threads() -> int:
        """Kill any leaked sandbox threads that survived a timeout.

        Uses ``ctypes.pythonapi.PyThreadState_SetAsyncExc`` to inject
        ``SystemExit`` into threads whose name starts with ``sandbox``.
        This is the standard CPython pattern for async thread termination.

        Returns:
            Number of threads terminated.
        """
        killed = 0
        for thread in threading.enumerate():
            if thread.name.startswith("sandbox") and thread.is_alive():
                try:
                    exc = ctypes.py_object(SystemExit)
                    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(
                        ctypes.c_long(thread.ident), exc
                    )
                    if res == 1:
                        killed += 1
                        logger.debug("Terminated stuck sandbox thread %s", thread.name)
                    elif res > 1:
                        # Something went wrong — undo the damage
                        ctypes.pythonapi.PyThreadState_SetAsyncExc(
                            ctypes.c_long(thread.ident), None
                        )
                        logger.warning(
                            "PyThreadState_SetAsyncExc returned %d for thread %s; undoing",
                            res, thread.name,
                        )
                except Exception:
                    logger.debug("Could not terminate sandbox thread %s", thread.name, exc_info=True)
        return killed

    async def execute(self, code: str, args: dict | None = None, timeout_ms: int = 5000) -> dict:
        """Compile and run *code* with *args* in a RestrictedPython sandbox.

        If *code* defines a ``main`` function, it is called with **args and the
        return value is captured. Otherwise, the locals dict (less dunders) is
        returned as the result.

        Parameters:
            code: Python expression or function definition.
            args: Keyword arguments to pass to ``main()`` or inject as locals.
            timeout_ms: Maximum wall-clock time for execution in milliseconds.

        Returns:
            dict with keys: ``result`` (the return value), ``output`` (captured stdout).

        Raises:
            SandboxSecurityViolation: forbidden operation detected.
            SandboxTimeout: execution exceeded *timeout_ms*.
            SandboxError: compilation or runtime error.
        """
        args = args or {}

        # 1. Compile with RestrictedPython — try eval first (for expressions),
        #    fall back to exec (for statements/function defs).
        try:
            bytecode = compile_restricted(code, "<code_snippet>", "eval")
            mode = "eval"
        except SyntaxError:
            try:
                bytecode = compile_restricted(code, "<code_snippet>", "exec")
                mode = "exec"
            except SyntaxError as exc:
                raise SandboxError(f"Syntax error in code snippet: {exc}") from exc

        # 2. Build execution namespace — inject args
        safe_locals: dict = dict(args)

        # 3. Run with timeout via explicit thread pool so threads can be
        #    abandoned on timeout (avoids 300s default executor thread cleanup).
        loop = asyncio.get_running_loop()
        pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="sandbox")
        try:
            await asyncio.wait_for(
                loop.run_in_executor(pool, self._run_bytecode, bytecode, safe_locals, mode),
                timeout=timeout_ms / 1000.0,
            )
        except asyncio.TimeoutError:
            logger.warning("Sandbox execution timed out after %d ms", timeout_ms)
            pool.shutdown(wait=False, cancel_futures=True)
            # Kill any leaked sandbox threads that survived the timeout.
            # ThreadPoolExecutor.shutdown(wait=False) cannot terminate a
            # running thread — if the sandboxed code is stuck in an infinite
            # loop, the thread keeps spinning and hogs the GIL, starving the
            # rest of the test suite.  We forcibly inject SystemExit.
            self._terminate_sandbox_threads()
            raise SandboxTimeout(f"Code execution timed out after {timeout_ms} ms.")
        finally:
            # Ensure pool is always shut down (no-op if already shut down).
            pool.shutdown(wait=False)

        # 4. Extract result and captured print output
        #    exec mode: RestrictedPython injects _print = PrintCollector(_getattr_)
        #    at the top of the module.  print() calls are captured in _print.txt.
        output = ""
        if mode == "exec":
            print_collector = safe_locals.get("_print")
            if print_collector is not None:
                output = print_collector()

        # eval mode: result is the return value of _run_bytecode
        if mode == "eval":
            return {
                "result": safe_locals.get("__eval_result__"),
                "output": output,
            }

        # exec mode: if 'main' is defined, call it with args
        if "main" in safe_locals and callable(safe_locals["main"]):
            try:
                main_result = safe_locals["main"](**args)
                return {
                    "result": main_result,
                    "output": output,
                }
            except Exception as exc:
                raise SandboxError(f"Error calling main(): {exc}") from exc

        # No main function — return visible locals
        visible_locals = {
            k: v
            for k, v in safe_locals.items()
            if not k.startswith("_") and k not in args
        }
        return {
            "result": safe_locals if not visible_locals else visible_locals,
            "output": output,
        }

    def _run_bytecode(self, bytecode, safe_locals: dict, mode: str = "exec") -> None:
        """Execute compiled bytecode in the sandbox globals/locals.

        Runs synchronously (called via ``asyncio.to_thread`` for timeout safety).
        Catches NameError/ImportError (forbidden name/module access) and
        re-raises as SandboxSecurityViolation.

        In eval mode, the result is stored in ``safe_locals["__eval_result__"]``.
        """
        try:
            if mode == "eval":
                result = eval(bytecode, self._safe_globals, safe_locals)
                safe_locals["__eval_result__"] = result
            else:
                exec(bytecode, self._safe_globals, safe_locals)
        except ImportError as exc:
            logger.warning("Sandbox blocked import attempt: %s", exc)
            raise SandboxSecurityViolation(f"Forbidden operation: import is not allowed ({exc})") from exc
        except NameError as exc:
            logger.warning("Sandbox blocked name access: %s", exc)
            raise SandboxSecurityViolation(f"Forbidden operation: {exc}") from exc
        except PermissionError as exc:
            logger.warning("Sandbox blocked permission-restricted operation: %s", exc)
            raise SandboxSecurityViolation(f"Forbidden operation: {exc}") from exc
