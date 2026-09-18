from django.apps import AppConfig


class GradevanceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "gradevance"
    verbose_name = "GradeVance"

    def ready(self):
        # Domain AI registers via ai.domain.register_builtin_domains — not here
        # (RULE_3: hosted app must not own Pulse registration side-effects that
        # import ai at import-time in a way that couples app load order).
        pass
