"""GradeVance domain AI registration smoke."""
from __future__ import annotations

from ai.domain import register_builtin_domains
from ai.domain_protocol import get_domain, has_domain


def test_gradevance_domain_registers():
    register_builtin_domains()
    assert has_domain("gradevance") is True
    domain_cls = get_domain("gradevance")
    domain = domain_cls()
    assert domain.app_display_name == "GradeVance"
    assert "chat" in domain.supported_task_types
    ctx = domain.get_domain_context()
    assert "translation_device" in ctx.domain_knowledge["concepts"]
    ok, _ = domain.validate_task_payload("chat", {"table_id": "x"})
    assert ok is False
