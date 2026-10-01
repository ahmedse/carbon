from django.apps import AppConfig


class PeopleConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'people'
    verbose_name = 'People & Payroll'

    def ready(self):
        import people.compliance  # noqa: registers evaluators into regulations.registry
        import people.signals  # noqa: registers correspondence -> Loan/Leave status sync
        from people.inbound_cartridges import register_people_cartridges
        from people.policy_plane import register as register_policy_plane
        register_people_cartridges()
        register_policy_plane()
