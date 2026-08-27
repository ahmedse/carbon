"""Swagger/OpenAPI schema documentation tests (drf-spectacular, ADR 0003).

EPH-5C migrated API docs from drf-yasg to drf-spectacular:

- Schema endpoint:  GET /carbon-api/schema/          (SpectacularAPIView)
- Swagger UI:       GET /carbon-api/schema/swagger-ui/
- ReDoc:            GET /carbon-api/schema/redoc/

The schema endpoints are NOT dev-gated anymore (drf-spectacular is import-safe
in every environment) and are protected by AdminOrSuperuserOnly — so these
tests authenticate as a superuser instead of a plain user.
"""

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()


class SwaggerDocumentationTests(APITestCase):
    def setUp(self):
        # Schema endpoints are gated by AdminOrSuperuserOnly (ADR 0003):
        # plain users get 403, superusers pass.
        self.user = User.objects.create_superuser(username='docs-admin', password='pass123')

    def test_swagger_schema_contains_documented_operations(self):
        self.client.force_authenticate(user=self.user)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.get(f'/{api_prefix}/schema/?format=json')
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        paths = schema.get('paths', {})

        # --- MDM reference-set custom actions ---
        self.assertIn('/mdm/reference-sets/{id}/values/', paths)
        self.assertIn('/mdm/reference-sets/{id}/transition/', paths)
        self.assertIn('/mdm/reference-sets/archive-bulk/', paths)

        # --- MDM org-unit hierarchy actions ---
        self.assertIn('/mdm/org-units/{id}/tree/', paths)
        self.assertIn('/mdm/org-units/tree/', paths)
        self.assertIn('/mdm/org-units/{id}/ancestors/', paths)

        # --- MDM field binding ---
        self.assertIn('/mdm/bind-field/', paths)

        # --- DQ custom actions ---
        # Phase 5 removed the synchronous execute action; run now creates a job.
        self.assertIn('/dq/rules/{id}/run/', paths)
        self.assertIn('/dq/rules/{id}/history/', paths)
        self.assertIn('/dq/results/{id}/failures/', paths)

        # --- DQ profile / run endpoints ---
        self.assertIn('/dq/profile/', paths)
        self.assertIn('/dq/profile/bulk/', paths)
        self.assertIn('/dq/run/', paths)
        self.assertIn('/dq/run-validation/', paths)

        # --- DQ metrics ---
        self.assertIn('/dq/metrics/', paths)
        self.assertIn('/dq/metrics/table/{table_id}/', paths)
        self.assertIn('/dq/metrics/field/{field_id}/', paths)

        # --- Catalog bulk and governance ---
        self.assertIn('/catalog/assets/archive-bulk/', paths)
        self.assertIn('/catalog/governance/compliance/', paths)
        self.assertIn('/catalog/governance-events/', paths)

    def test_key_operations_have_descriptions(self):
        """Documented operations must carry non-empty descriptions."""
        self.client.force_authenticate(user=self.user)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.get(f'/{api_prefix}/schema/?format=json')
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        paths = schema.get('paths', {})

        check = [
            ('/mdm/reference-sets/{id}/values/', 'get'),
            ('/mdm/reference-sets/{id}/transition/', 'post'),
            ('/mdm/reference-sets/archive-bulk/', 'post'),
            ('/mdm/org-units/{id}/tree/', 'get'),
            ('/mdm/org-units/tree/', 'get'),
            ('/mdm/org-units/{id}/ancestors/', 'get'),
            ('/dq/rules/{id}/run/', 'post'),
            ('/dq/profile/', 'post'),
            ('/dq/run/', 'post'),
            ('/dq/metrics/', 'get'),
            ('/catalog/assets/archive-bulk/', 'post'),
        ]
        for path, method in check:
            with self.subTest(path=path, method=method):
                op = paths.get(path, {}).get(method, {})
                self.assertTrue(
                    op.get('description', '').strip(),
                    msg=f'{method.upper()} {path} has no description in OpenAPI schema',
                )

    def test_schema_requires_admin_auth(self):
        """ADR 0003: schema endpoints run in production but are admin-only."""
        api_prefix = settings.API_PREFIX.strip('/')
        anon = self.client.get(f'/{api_prefix}/schema/?format=json')
        self.assertIn(anon.status_code, (401, 403))

        plain = User.objects.create_user(username='docs-user', password='pass123')
        self.client.force_authenticate(user=plain)
        denied = self.client.get(f'/{api_prefix}/schema/?format=json')
        self.assertEqual(denied.status_code, 403)
