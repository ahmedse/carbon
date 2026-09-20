"""Tests for pulse UX telemetry (fail-soft)."""
from ai.pulse_ux_telemetry import emit_ux


def test_emit_ux_never_raises():
    emit_ux("")
    emit_ux("agent.scope_route", cls="PLAN_CLEAR", message="secret should be dropped")
    emit_ux("chat.deixis_gate", has_topic=True)
