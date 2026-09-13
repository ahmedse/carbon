from django.apps import AppConfig


class PeopleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'people'
    verbose_name = 'People & Payroll'

    def ready(self):
        import people.compliance  # noqa: registers evaluators into regulations.registry
        import people.signals  # noqa: registers correspondence -> Loan status sync
