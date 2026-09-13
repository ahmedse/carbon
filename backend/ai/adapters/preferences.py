"""DjangoUserPreferenceAdapter — host implementation of the UserPreferenceStore port.

Reads and writes ``ai.models.workspace.AIUserProfile`` preference columns
directly through the Django ORM (synchronous, keyed by ``host_user_id``),
matching the pre-migration ``SessionPreferenceStore`` behavior exactly.
"""
from __future__ import annotations

from ai.models import AIUserProfile


class DjangoUserPreferenceAdapter:
    """Durable per-user preference adapter implementing ``UserPreferenceStore``."""

    def __init__(self) -> None:
        pass

    def get_preferences(self, host_user_id: str) -> dict[str, str]:
        profile, _ = AIUserProfile.objects.get_or_create(user_id=host_user_id)
        return {
            "verbosity": profile.pref_verbosity,
            "format": profile.pref_format,
            "depth": profile.pref_depth,
        }

    def save_preferences(self, host_user_id: str, prefs: dict[str, str]) -> None:
        profile, _ = AIUserProfile.objects.get_or_create(user_id=host_user_id)
        profile.pref_verbosity = prefs["verbosity"]
        profile.pref_format = prefs["format"]
        profile.pref_depth = prefs["depth"]
        profile.save(
            update_fields=[
                "pref_verbosity",
                "pref_format",
                "pref_depth",
                "updated_at",
            ]
        )

    def reset_preferences(self, host_user_id: str) -> None:
        AIUserProfile.objects.filter(user_id=host_user_id).update(
            pref_verbosity="normal",
            pref_format="mixed",
            pref_depth="normal",
        )
