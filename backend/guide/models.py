from django.db import models


class GuideProgress(models.Model):
    """Per-user microlearning progress for any domain pack.

    Stores lesson identity and state only: no domain figure, no answer text, no
    copy of host data. ``pack_id`` is the pack that owns the lesson
    (``_platform`` or a domain pack id), so one table serves
    every domain app and a new app needs no migration.

    While ``state`` is ``started`` and ``signal`` is ``answer``, the user's
    answer is accepted and the lesson is only waiting for its host check.
    """

    STATE_CHOICES = [
        ("offered", "Offered"),
        ("started", "Started"),
        ("done", "Done"),
        ("snoozed", "Snoozed"),
    ]
    SIGNAL_CHOICES = [
        ("host_row", "Host row"),
        ("host_state", "Host state"),
        ("answer", "Answer"),
    ]

    user = models.ForeignKey(
        "accounts.User", on_delete=models.PROTECT, related_name="guide_progress"
    )
    pack_id = models.CharField(max_length=40)
    lesson_id = models.CharField(max_length=24)
    lesson_version = models.PositiveSmallIntegerField(default=1)
    state = models.CharField(max_length=10, choices=STATE_CHOICES, default="offered")
    started_at = models.DateTimeField(null=True, blank=True)
    done_at = models.DateTimeField(null=True, blank=True)
    snoozed_until = models.DateTimeField(null=True, blank=True)
    signal = models.CharField(max_length=12, choices=SIGNAL_CHOICES, blank=True, default="")
    step = models.PositiveSmallIntegerField(
        default=0,
        help_text="Coach card 0–3 (know, do, check, after). Last place the caller stopped.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "pack_id", "lesson_id"], name="uniq_guide_user_pack_lesson"
            ),
        ]
        indexes = [models.Index(fields=["user", "pack_id", "state"])]

    def __str__(self):
        return f"{self.user_id}:{self.pack_id}:{self.lesson_id}:{self.state}"
