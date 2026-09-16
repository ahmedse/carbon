"""W-2 — sandboxed boolean guard expressions for workflow edges.

Grammar (RULE_20 safe, no ``eval`` / no imports / no attribute calls)::

    expr  := or_expr
    or_expr := and_expr ( 'or' and_expr )*
    and_expr := not_expr ( 'and' not_expr )*
    not_expr := 'not' not_expr | comparison
    comparison := atom ( ('=='|'!='|'<'|'>'|'<='|'>='|'in') atom )?
    atom := NUMBER | STRING | TRUE | FALSE | NULL | path | '(' expr ')'
    path := NAME ( '.' NAME | '[' NUMBER|STRING ']' )*

Context is a plain dict; dotted paths walk nested dicts/lists. Injection
attempts (``__``, ``import``, call-like ``(`` after a path) are refused.
"""

from __future__ import annotations

import re
from typing import Any

__all__ = ["GuardError", "eval_guard"]


class GuardError(ValueError):
    """Raised when a guard expression is invalid or unsafe."""


_TRUE = frozenset({"true", "True", "TRUE"})
_FALSE = frozenset({"false", "False", "FALSE"})
_NULL = frozenset({"null", "None", "none", "NULL"})
_FORBIDDEN = re.compile(r"__|import\b|exec\b|eval\b|lambda\b|globals\b|locals\b")


class _Tok:
    __slots__ = ("kind", "value")

    def __init__(self, kind: str, value: Any = None):
        self.kind = kind
        self.value = value


def _tokenize(src: str) -> list[_Tok]:
    if _FORBIDDEN.search(src or ""):
        raise GuardError("guard expression contains forbidden tokens")
    s = (src or "").strip()
    if not s:
        raise GuardError("empty guard")
    toks: list[_Tok] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c.isspace():
            i += 1
            continue
        if c in "()[]":
            toks.append(_Tok(c))
            i += 1
            continue
        if c == ".":
            toks.append(_Tok("."))
            i += 1
            continue
        if c in "'\"":
            quote = c
            j = i + 1
            buf = []
            while j < n and s[j] != quote:
                if s[j] == "\\" and j + 1 < n:
                    buf.append(s[j + 1])
                    j += 2
                    continue
                buf.append(s[j])
                j += 1
            if j >= n:
                raise GuardError("unterminated string")
            toks.append(_Tok("STR", "".join(buf)))
            i = j + 1
            continue
        if c.isdigit() or (c == "-" and i + 1 < n and s[i + 1].isdigit()):
            j = i + 1
            while j < n and (s[j].isdigit() or s[j] == "."):
                j += 1
            raw = s[i:j]
            toks.append(_Tok("NUM", float(raw) if "." in raw else int(raw)))
            i = j
            continue
        if c.isalpha() or c == "_":
            j = i + 1
            while j < n and (s[j].isalnum() or s[j] == "_"):
                j += 1
            word = s[i:j]
            if word in ("and", "or", "not", "in"):
                toks.append(_Tok(word))
            elif word in _TRUE:
                toks.append(_Tok("BOOL", True))
            elif word in _FALSE:
                toks.append(_Tok("BOOL", False))
            elif word in _NULL:
                toks.append(_Tok("NULL", None))
            else:
                toks.append(_Tok("NAME", word))
            i = j
            continue
        if s.startswith("==", i) or s.startswith("!=", i) or s.startswith("<=", i) or s.startswith(">=", i):
            toks.append(_Tok("OP", s[i : i + 2]))
            i += 2
            continue
        if c in "<>":
            toks.append(_Tok("OP", c))
            i += 1
            continue
        raise GuardError(f"unexpected character {c!r} at {i}")
    return toks


class _Parser:
    def __init__(self, toks: list[_Tok], ctx: dict):
        self.toks = toks
        self.i = 0
        self.ctx = ctx

    def _peek(self) -> _Tok | None:
        return self.toks[self.i] if self.i < len(self.toks) else None

    def _eat(self, kind: str | None = None) -> _Tok:
        tok = self._peek()
        if tok is None:
            raise GuardError("unexpected end of guard")
        if kind is not None and tok.kind != kind:
            raise GuardError(f"expected {kind}, got {tok.kind}")
        self.i += 1
        return tok

    def parse(self) -> Any:
        val = self._or()
        if self._peek() is not None:
            raise GuardError(f"trailing tokens after guard: {self._peek().kind}")
        return val

    def _or(self) -> Any:
        left = self._and()
        while self._peek() and self._peek().kind == "or":
            self._eat("or")
            right = self._and()
            left = bool(left) or bool(right)
        return left

    def _and(self) -> Any:
        left = self._not()
        while self._peek() and self._peek().kind == "and":
            self._eat("and")
            right = self._not()
            left = bool(left) and bool(right)
        return left

    def _not(self) -> Any:
        if self._peek() and self._peek().kind == "not":
            self._eat("not")
            return not bool(self._not())
        return self._comparison()

    def _comparison(self) -> Any:
        left = self._atom()
        tok = self._peek()
        if tok and tok.kind == "OP":
            op = self._eat("OP").value
            right = self._atom()
            if op == "==":
                return left == right
            if op == "!=":
                return left != right
            if op == "<":
                return left < right
            if op == ">":
                return left > right
            if op == "<=":
                return left <= right
            if op == ">=":
                return left >= right
            raise GuardError(f"unknown operator {op}")
        if tok and tok.kind == "in":
            self._eat("in")
            right = self._atom()
            try:
                return left in right
            except TypeError as exc:
                raise GuardError(f"'in' requires a collection: {exc}") from exc
        return left

    def _atom(self) -> Any:
        tok = self._peek()
        if tok is None:
            raise GuardError("unexpected end of guard")
        if tok.kind == "(":
            self._eat("(")
            val = self._or()
            self._eat(")")
            return val
        if tok.kind == "NUM":
            return self._eat("NUM").value
        if tok.kind == "STR":
            return self._eat("STR").value
        if tok.kind == "BOOL":
            return self._eat("BOOL").value
        if tok.kind == "NULL":
            self._eat("NULL")
            return None
        if tok.kind == "NAME":
            return self._path()
        raise GuardError(f"unexpected token {tok.kind}")

    def _path(self) -> Any:
        name = self._eat("NAME").value
        if name.startswith("__"):
            raise GuardError("forbidden path")
        cur: Any = self.ctx.get(name)
        while True:
            tok = self._peek()
            if tok is None:
                break
            if tok.kind == ".":
                self._eat(".")
                key = self._eat("NAME").value
                if key.startswith("__"):
                    raise GuardError("forbidden path")
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(key)
                continue
            if tok.kind == "[":
                self._eat("[")
                idx_tok = self._eat()
                self._eat("]")
                if idx_tok.kind == "NUM":
                    if not isinstance(cur, (list, tuple)):
                        return None
                    idx = int(idx_tok.value)
                    cur = cur[idx] if 0 <= idx < len(cur) else None
                elif idx_tok.kind == "STR":
                    if not isinstance(cur, dict):
                        return None
                    cur = cur.get(idx_tok.value)
                else:
                    raise GuardError("index must be number or string")
                continue
            break
        # Refuse call-like syntax: path followed by '('
        if self._peek() and self._peek().kind == "(":
            raise GuardError("function calls are not allowed in guards")
        return cur


def eval_guard(expression: str, context: dict | None = None) -> bool:
    """Evaluate a guard expression against ``context``. Returns a bool."""
    toks = _tokenize(expression)
    parser = _Parser(toks, context or {})
    result = parser.parse()
    return bool(result)
