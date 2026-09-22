"""Signals for ``people`` — correspondence → domain subject sync.

Implementation lives in ``correspondence_subject_sync`` (terminal + void/reopen).
Imported from ``PeopleConfig.ready``.
"""

# noqa: F401 — side-effect import registers pre_save / post_save receivers
from . import correspondence_subject_sync as correspondence_subject_sync  # noqa: F401
