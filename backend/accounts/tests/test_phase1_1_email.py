# File: accounts/tests/test_phase1_1_email.py
# Phase 1.1 — Tests for EmailConfig, PasswordPolicy models and email test endpoint

import pytest
from django.urls import reverse
from rest_framework import status

from accounts.models import EmailConfig, PasswordPolicy


@pytest.mark.django_db
class TestEmailConfig:
    """Test the EmailConfig singleton model."""

    def test_singleton_creation(self):
        """load() should create a singleton with defaults."""
        cfg = EmailConfig.load()
        assert cfg.pk == 1
        assert cfg.backend == 'django.core.mail.backends.console.EmailBackend'
        assert cfg.enabled is True
        assert cfg.from_email == 'noreply@carbon.clearturn.tech'

    def test_singleton_only_one(self):
        """Only one EmailConfig row allowed."""
        cfg1 = EmailConfig.load()
        cfg2 = EmailConfig.load()
        assert cfg1.pk == cfg2.pk == 1
        assert EmailConfig.objects.count() == 1

    def test_save_preserves_singleton(self):
        """Saving a new instance overwrites the existing one."""
        cfg1 = EmailConfig.load()
        cfg1.from_email = 'test@example.com'
        cfg1.save()
        assert EmailConfig.objects.count() == 1
        cfg2 = EmailConfig.load()
        assert cfg2.from_email == 'test@example.com'

    def test_as_django_settings(self):
        """as_django_settings() returns a valid settings dict."""
        cfg = EmailConfig.load()
        cfg.backend = 'django.core.mail.backends.smtp.EmailBackend'
        cfg.host = 'smtp.example.com'
        cfg.port = 587
        cfg.username = 'user'
        cfg.password = 'pass'
        cfg.use_tls = True
        cfg.from_email = 'admin@example.com'
        cfg.from_name = 'Carbon'

        settings = cfg.as_django_settings()
        assert settings['EMAIL_BACKEND'] == 'django.core.mail.backends.smtp.EmailBackend'
        assert settings['EMAIL_HOST'] == 'smtp.example.com'
        assert settings['EMAIL_PORT'] == 587
        assert settings['EMAIL_HOST_USER'] == 'user'
        assert settings['EMAIL_HOST_PASSWORD'] == 'pass'
        assert settings['EMAIL_USE_TLS'] is True
        assert settings['EMAIL_USE_SSL'] is False
        assert settings['DEFAULT_FROM_EMAIL'] == 'Carbon <admin@example.com>'

    def test_as_django_settings_brevo(self):
        """Brevo backend sets the anymail API key."""
        cfg = EmailConfig.load()
        cfg.backend = 'anymail.backends.brevo.EmailBackend'
        cfg.password = 'xkeysib-api-key'
        settings = cfg.as_django_settings()
        assert settings['ANYMAIL']['SENDINBLUE_API_KEY'] == 'xkeysib-api-key'

    def test_disabled(self):
        """Email can be disabled."""
        cfg = EmailConfig.load()
        cfg.enabled = False
        cfg.save()
        cfg2 = EmailConfig.load()
        assert cfg2.enabled is False


@pytest.mark.django_db
class TestPasswordPolicy:
    """Test the PasswordPolicy singleton model."""

    def test_singleton_creation(self):
        """load() should create a singleton with sensible defaults."""
        policy = PasswordPolicy.load()
        assert policy.pk == 1
        assert policy.min_length == 12
        assert policy.require_uppercase is True
        assert policy.require_lowercase is True
        assert policy.require_number is True
        assert policy.require_special is True
        assert policy.max_age_days == 90
        assert policy.lockout_after_n == 5

    def test_singleton_only_one(self):
        """Only one PasswordPolicy row allowed."""
        p1 = PasswordPolicy.load()
        p2 = PasswordPolicy.load()
        assert p1.pk == p2.pk == 1
        assert PasswordPolicy.objects.count() == 1

    def test_custom_policy(self):
        """Policy values can be updated."""
        policy = PasswordPolicy.load()
        policy.min_length = 8
        policy.max_age_days = 0  # never expire
        policy.lockout_after_n = 3
        policy.save()

        reloaded = PasswordPolicy.load()
        assert reloaded.min_length == 8
        assert reloaded.max_age_days == 0
        assert reloaded.lockout_after_n == 3


@pytest.mark.django_db
class TestEmailTestEndpoint:
    """Test the /email/test/ admin diagnostic endpoint."""

    @property
    def url(self):
        from django.conf import settings
        api_prefix = settings.API_PREFIX.strip('/')
        return f'/{api_prefix}/email/test/'

    def test_requires_auth(self, api_client):
        """Unauthenticated requests are rejected."""
        response = api_client.post(self.url, {'to': 'test@example.com'}, format='json')
        assert response.status_code in (401, 403)

    def test_requires_admin(self, api_client, create_user, get_token_for_user):
        """Non-admin users cannot access."""
        user = create_user('staff')
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(user)}')
        response = api_client.post(self.url, {'to': 'test@example.com'}, format='json')
        assert response.status_code in (401, 403)

    def test_missing_to_field(self, api_client, create_user, get_token_for_user):
        """Missing 'to' returns 400."""
        admin = create_user('admin', is_staff=True, is_superuser=True)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(admin)}')
        response = api_client.post(self.url, {}, format='json')
        assert response.status_code == 400
        assert response.json()['error'] == 'Missing "to" field'

    def test_email_disabled(self, api_client, create_user, get_token_for_user):
        """Returns error when EmailConfig is disabled."""
        cfg = EmailConfig.load()
        cfg.enabled = False
        cfg.save()

        admin = create_user('admin', is_staff=True, is_superuser=True)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(admin)}')
        response = api_client.post(self.url, {'to': 'test@example.com'}, format='json')
        assert response.status_code == 500
        assert response.json()['success'] is False

    def test_console_backend_works(self, api_client, create_user, get_token_for_user):
        """Console email backend sends without error (emails go to stdout)."""
        cfg = EmailConfig.load()
        cfg.enabled = True
        cfg.backend = 'django.core.mail.backends.console.EmailBackend'
        cfg.save()

        admin = create_user('admin', is_staff=True, is_superuser=True)
        api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {get_token_for_user(admin)}')
        response = api_client.post(self.url, {'to': 'test@example.com'}, format='json')
        assert response.status_code == 200
        assert response.json()['success'] is True


@pytest.mark.django_db
class TestPasswordResetEndpoints:
    """Test the Django password reset flow is wired up."""

    def test_password_reset_get(self, client):
        """GET password_reset returns the reset form page."""
        url = reverse('password_reset')
        response = client.get(url)
        assert response.status_code == 200

    def test_password_reset_post(self, client, django_user_model):
        """POST password_reset sends an email for known users."""
        user = django_user_model.objects.create_user(
            username='testuser', email='test@example.com', password='password123'
        )
        url = reverse('password_reset')
        response = client.post(url, {'email': 'test@example.com'})
        # Redirects to done page on success
        assert response.status_code in (200, 302)
