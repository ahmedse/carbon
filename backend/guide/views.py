"""Guide HTTP surface: ``/guide/<app_id>/…``. Reads the caller's own scope; writes GuideProgress only."""
from __future__ import annotations

from django.conf import settings
from django.utils import timezone
from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from guide import engine, packs


class GuideAppPermission(BasePermission):
    """The domain app must be enabled for this brand and not switched off at runtime."""

    message = "This app is not enabled for this instance."

    def has_permission(self, request, view):
        app_id = view.kwargs.get("app_id", "")
        brand = getattr(settings, "DJANGO_BRAND", "aastmt")
        presets = getattr(settings, "BRAND_APP_PRESETS", {}) or {}
        if not presets.get(brand, {}).get(app_id):
            return False
        from accounts.models import PlatformAppConfig

        return not PlatformAppConfig.objects.filter(app_id=app_id, is_enabled=False).exists()


def _lang(request) -> str:
    lang = request.query_params.get("lang") or getattr(request.user, "language", "") or packs.FALLBACK
    return lang if lang in packs.LANGUAGES else packs.FALLBACK


def _fill(text, params: dict) -> str:
    text = str(text or "")
    for key, value in params.items():
        text = text.replace("{" + key + "}", str(value))
    return text


def _setup(request, app_id):
    """(ctx, catalog) or None when the app has no guide pack."""
    from accounts.capabilities import get_user_capabilities

    if not packs.has_pack(app_id):
        return None
    catalog = packs.catalog_for(app_id)
    ctx = engine.Ctx(request.user, app_id, frozenset(get_user_capabilities(request.user)))
    return ctx, [row for row in catalog if engine.is_available(row, ctx)]


def _pack_ids(available) -> set[str]:
    return {row["pack"] for row in available}


def _listing(ctx, available, now):
    return engine.evaluate_lessons(ctx, available, engine.load_progress(ctx.user, _pack_ids(available)), now)


class GuideListAPIView(APIView):
    """GET the caller's tracks, lessons, blockers and next lesson."""

    permission_classes = [IsAuthenticated, GuideAppPermission]

    def get(self, request, app_id):
        setup = _setup(request, app_id)
        if setup is None:
            return Response({"detail": "No guide for this app."}, status=404)
        ctx, available = setup
        copy = packs.copy_for(app_id, _lang(request))
        listing = _listing(ctx, available, timezone.now())
        for row in listing["tracks"]:
            row.update({k: v for k, v in (copy.get("tracks", {}).get(row["id"]) or {}).items() if k in ("title", "blurb")})
        for row in listing["lessons"]:
            row["title"] = (copy.get("lessons", {}).get(row["id"]) or {}).get("title", row["id"])
            if row["blocker"]:
                row["blocker"] = {**row["blocker"], **(copy.get("blockers", {}).get(row["blocker"]["code"]) or {})}
        listing["app_id"] = app_id
        return Response(listing)


class GuideDetailAPIView(APIView):
    """GET one lesson with its live object, question and text. 404 if the caller may not take it."""

    permission_classes = [IsAuthenticated, GuideAppPermission]

    def get(self, request, app_id, lesson_id):
        setup = _setup(request, app_id)
        lesson = next((r for r in setup[1] if r["id"] == lesson_id), None) if setup else None
        if lesson is None:
            return Response({"detail": "Lesson not found."}, status=404)
        ctx, available = setup
        now = timezone.now()
        summary = next(r for r in _listing(ctx, available, now)["lessons"] if r["id"] == lesson_id)
        question = engine.question_for(lesson, ctx)
        text = dict((packs.copy_for(app_id, _lang(request)).get("lessons", {}).get(lesson_id)) or {})
        params = question["params"]
        for key in ("title", "know", "do", "dont", "question", "explain"):
            text[key] = _fill(text.get(key), params)
        text["options"] = [_fill(opt, params) for opt in (text.get("options") or [])][: question["options"]]
        summary.update({
            "live": engine.live_object(lesson, ctx),
            "question": question,
            "host_required": bool(lesson.get("host")),
            "copy": text,
        })
        return Response(summary)


class GuideProgressAPIView(APIView):
    """POST a progress event. Writes ``GuideProgress`` only."""

    permission_classes = [IsAuthenticated, GuideAppPermission]
    EVENTS = ("started", "answered", "check", "snooze", "opened")

    def post(self, request, app_id, lesson_id):
        setup = _setup(request, app_id)
        lesson = next((r for r in setup[1] if r["id"] == lesson_id), None) if setup else None
        if lesson is None:
            return Response({"detail": "Lesson not found."}, status=404)
        ctx, available = setup
        event = request.data.get("event")
        if event not in self.EVENTS:
            return Response({"detail": "event must be one of " + ", ".join(self.EVENTS)}, status=400)
        choice = request.data.get("choice")
        if event == "answered" and (lesson.get("question") or {}).get("kind") == "host":
            return Response({"detail": "This lesson is checked in the app, not by a choice."}, status=400)
        if event == "answered":
            limit = engine.question_for(lesson, ctx)["options"]
            if isinstance(choice, bool) or not isinstance(choice, int) or not 0 <= choice < limit:
                return Response({"detail": f"choice must be an integer 0 to {limit - 1}."}, status=400)
        else:
            choice = None
        step = request.data.get("step")
        if step is None:
            parsed_step = None
        elif isinstance(step, bool) or not isinstance(step, int) or not 0 <= step <= engine.STEP_MAX:
            return Response({"detail": f"step must be an integer 0 to {engine.STEP_MAX}."}, status=400)
        else:
            parsed_step = step
        now = timezone.now()
        out = engine.apply_event(ctx, lesson, event, choice, now, parsed_step)
        listing = _listing(ctx, available, now)
        out["next_id"] = listing["next_id"]
        out["resume"] = listing["resume"]
        return Response(out)
