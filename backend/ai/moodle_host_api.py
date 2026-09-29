"""HTTP door: Moodle PHP → Pulse chat spine. HMAC, Ask-only, no Django user."""
from __future__ import annotations

import json
import logging

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from ai.moodle_host import (
    INSTANCE_ID,
    configured_secret,
    issue_ticket,
    prepare_ask,
    prepare_embed,
    take_ticket,
    verify_signature,
)

logger = logging.getLogger("carbon.ai.moodle_host")


def _answer_from_dispatch(result: dict) -> str:
    body = result.get("result") if isinstance(result, dict) else None
    if not isinstance(body, dict):
        return ""
    return str(body.get("content") or "").strip()


@method_decorator(csrf_exempt, name="dispatch")
class MoodleAskView(APIView):
    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        secret = configured_secret(getattr(settings, "MOODLE_PULSE_HMAC_SECRET", "") or "")
        raw = request.body or b""
        if not verify_signature(
            secret,
            request.headers.get("X-Pulse-Timestamp", ""),
            raw,
            request.headers.get("X-Pulse-Signature", ""),
        ):
            return Response({"ok": False, "error": "unauthorized"}, status=401)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({"ok": False, "error": "bad_json"}, status=400)
        if not isinstance(payload, dict):
            return Response({"ok": False, "error": "bad_json"}, status=400)
        decision = prepare_ask(payload)
        if decision.error:
            return Response({"ok": False, "error": decision.error}, status=decision.status)
        if not decision.chat:
            body = {
                "ok": True,
                "engine": "pulse",
                "pulse_mode": "ask",
                "instance_id": INSTANCE_ID,
                "answer": decision.answer or "",
            }
            if decision.refusal:
                body["refusal"] = decision.refusal
            return Response(body)
        chat = decision.chat

        from ai.engine_runtime import dispatch_task

        result = dispatch_task("chat", chat, instance_id=INSTANCE_ID)
        if not isinstance(result, dict) or result.get("status") != "completed":
            logger.warning("Moodle chat spine status=%s", (result or {}).get("status"))
            return Response({"ok": False, "error": "engine_unavailable"}, status=503)
        answer = _answer_from_dispatch(result)
        if not answer:
            return Response({"ok": False, "error": "empty"}, status=503)
        return Response({
            "ok": True,
            "engine": "pulse",
            "pulse_mode": "ask",
            "instance_id": INSTANCE_ID,
            "answer": answer,
        })


def _moodle_host_user(moodle_user_id: str):
    """Shadow account so the real Pulse pane can open without a Carbon login.

    Conversations stay on this user. The engine instance is aast-med because
    the conversation app identifier is moodle.
    """
    from django.contrib.auth import get_user_model

    username = f"moodle-{moodle_user_id}"[:150]
    User = get_user_model()
    user = User.objects.filter(username=username).first()
    if user is None:
        user = User(username=username, email=f"{username}@localhost", is_active=True)
        user.set_unusable_password()
        user.save()
    return user


@method_decorator(csrf_exempt, name="dispatch")
class MoodleEmbedView(APIView):
    """Moodle asks for a one-time ticket. The browser redeems it for the pane."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        secret = configured_secret(getattr(settings, "MOODLE_PULSE_HMAC_SECRET", "") or "")
        raw = request.body or b""
        if not verify_signature(
            secret,
            request.headers.get("X-Pulse-Timestamp", ""),
            raw,
            request.headers.get("X-Pulse-Signature", ""),
        ):
            return Response({"ok": False, "error": "unauthorized"}, status=401)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return Response({"ok": False, "error": "bad_json"}, status=400)
        if not isinstance(payload, dict):
            return Response({"ok": False, "error": "bad_json"}, status=400)
        decision = prepare_embed(payload)
        if decision.error:
            return Response({"ok": False, "error": decision.error, "pulse_mode": "ask"}, status=decision.status)
        ticket = issue_ticket(
            decision.answer or "",
            payload.get("moodle_user_id"),
        )
        return Response({"ok": True, "ticket": ticket, "pulse_mode": "ask", "instance_id": INSTANCE_ID})


@method_decorator(csrf_exempt, name="dispatch")
class MoodleEmbedSessionView(APIView):
    """Redeem a ticket for a short-lived session the Pulse pane already understands."""

    authentication_classes: list = []
    permission_classes = [AllowAny]

    def post(self, request):
        ticket = ""
        try:
            body = request.data if isinstance(request.data, dict) else {}
            ticket = str(body.get("ticket") or "")
        except Exception:
            ticket = ""
        payload = take_ticket(ticket)
        if not payload:
            return Response({"ok": False, "error": "ticket"}, status=401)
        from rest_framework_simplejwt.tokens import RefreshToken

        user = _moodle_host_user(str(payload.get("moodle_user_id") or "0"))
        refresh = RefreshToken.for_user(user)
        return Response({
            "ok": True,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "username": user.username,
            "pulse_mode": "ask",
            "instance_id": INSTANCE_ID,
            "app_identifier": "moodle",
            "page_context": payload.get("page_context") or "",
        })
