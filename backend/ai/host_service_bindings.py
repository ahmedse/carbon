"""Register host implementations on the engine service seam.

Imported from ``AIConfig.ready``. The engine never imports this module.
"""
from __future__ import annotations

from ai.engine.host_services import (
    EnvelopeWriteError,
    set_active_process_definition,
    set_commit_proposal,
    set_daily_budget_override,
    set_emit_ux,
    set_fallback_envelope,
    set_fill_write_body,
    set_format_host_actions,
    set_labeled_numeric_points,
    set_localdate,
    set_propose_plan,
    set_synthesize_envelope,
    set_write_slots_for,
)


def bind_host_services() -> None:
    """Point every engine host call at the Django implementation."""

    def _localdate():
        from django.utils import timezone

        return timezone.localdate()

    def _fill_write_body(body, *, slots, text="", today=None):
        from ai.write_slots import fill_write_body

        return fill_write_body(body, slots=slots, text=text, today=today)

    def _write_slots_for(api_name, api_catalog):
        from ai.write_slots import write_slots_for

        return write_slots_for(api_name, api_catalog)

    def _format_host_actions(outputs):
        from ai.host_receipt import collect_navigate_actions, format_actions_markdown

        return format_actions_markdown(collect_navigate_actions(outputs))

    async def _synthesize_envelope(**kwargs):
        from ai.envelope_service import EnvelopeWriteError as HostWriteError
        from ai.envelope_service import synthesize_envelope

        try:
            return await synthesize_envelope(**kwargs)
        except HostWriteError as exc:
            raise EnvelopeWriteError(exc.cause) from exc

    def _fallback_envelope(usable, user_message):
        from ai.envelope_service import _deterministic_fallback_envelope

        return _deterministic_fallback_envelope(usable, user_message)

    def _labeled_numeric_points(rows):
        from ai.envelope_service import labeled_numeric_points

        return labeled_numeric_points(rows)

    def _active_process_definition(process_id: str):
        from ai.models.process import STATUS_ACTIVE, ProcessDefinition

        obj = (
            ProcessDefinition.objects.filter(
                process_id=process_id, status=STATUS_ACTIVE,
            )
            .order_by("-created_at")
            .first()
        )
        if obj and isinstance(obj.definition, dict):
            return obj.definition
        return None

    def _emit_ux(event, **kwargs):
        from ai.pulse_ux_telemetry import emit_ux

        emit_ux(event, **kwargs)

    def _commit_proposal(host_user_id, conversation_id):
        from django.contrib.auth import get_user_model

        from ai.plans_service import PlansService

        User = get_user_model()
        try:
            user = User.objects.get(pk=host_user_id)
        except (User.DoesNotExist, ValueError):
            return None
        return PlansService().commit_proposal(user, conversation_id or "")

    def _propose_plan(host_user_id, brief, *, conversation_id, prior_plan, revision):
        from django.contrib.auth import get_user_model

        from ai.plans_service import PlansService

        User = get_user_model()
        try:
            user = User.objects.get(pk=host_user_id)
        except (User.DoesNotExist, ValueError):
            return None, None
        return PlansService().propose_plan(
            user,
            brief,
            conversation_id=conversation_id or "",
            prior_plan=prior_plan,
            revision=revision,
            single_read=True,
        )

    def _daily_budget_override(instance_id: str):
        from ai.models.control_state import PulseControlState

        state = PulseControlState.objects.filter(instance_id=instance_id).first()
        if state is not None and state.daily_budget_usd is not None:
            return float(state.daily_budget_usd)
        return None

    set_localdate(_localdate)
    set_fill_write_body(_fill_write_body)
    set_write_slots_for(_write_slots_for)
    set_format_host_actions(_format_host_actions)
    set_synthesize_envelope(_synthesize_envelope)
    set_fallback_envelope(_fallback_envelope)
    set_labeled_numeric_points(_labeled_numeric_points)
    set_active_process_definition(_active_process_definition)
    set_emit_ux(_emit_ux)
    set_commit_proposal(_commit_proposal)
    set_propose_plan(_propose_plan)
    set_daily_budget_override(_daily_budget_override)
