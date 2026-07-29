from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase

User = get_user_model()


class SwaggerDocumentationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='docs-user', password='pass123')

    def test_swagger_schema_contains_documented_operations(self):
        self.client.force_authenticate(user=self.user)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.get(f'/{api_prefix}/swagger/?format=openapi')
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        paths = schema.get('paths', {})

        # --- MDM reference-set custom actions ---
        self.assertIn('/carbon-api/mdm/reference-sets/{id}/values/', paths)
        self.assertIn('/carbon-api/mdm/reference-sets/{id}/transition/', paths)
        self.assertIn('/carbon-api/mdm/reference-sets/archive-bulk/', paths)

        # --- MDM org-unit hierarchy actions ---
        self.assertIn('/carbon-api/mdm/org-units/{id}/tree/', paths)
        self.assertIn('/carbon-api/mdm/org-units/{id}/ancestors/', paths)

        # --- MDM field binding ---
        self.assertIn('/carbon-api/mdm/bind-field/', paths)

        # --- DQ custom actions ---
        self.assertIn('/carbon-api/dq/rules/{id}/execute/', paths)
        self.assertIn('/carbon-api/dq/rules/{id}/history/', paths)
        self.assertIn('/carbon-api/dq/results/{id}/failures/', paths)

        # --- DQ profile / run endpoints ---
        self.assertIn('/carbon-api/dq/profile/', paths)
        self.assertIn('/carbon-api/dq/profile/bulk/', paths)
        self.assertIn('/carbon-api/dq/run/', paths)
        self.assertIn('/carbon-api/dq/run-validation/', paths)

        # --- DQ metrics ---
        self.assertIn('/carbon-api/dq/metrics/', paths)
        self.assertIn('/carbon-api/dq/metrics/table/{table_id}/', paths)
        self.assertIn('/carbon-api/dq/metrics/field/{field_id}/', paths)

        # --- Catalog bulk and governance ---
        self.assertIn('/carbon-api/catalog/assets/archive-bulk/', paths)
        self.assertIn('/carbon-api/catalog/governance/compliance/', paths)
        self.assertIn('/carbon-api/catalog/governance-events/', paths)

    def test_key_operations_have_descriptions(self):
        """Documented operations must carry non-empty descriptions."""
        self.client.force_authenticate(user=self.user)
        api_prefix = settings.API_PREFIX.strip('/')

        response = self.client.get(f'/{api_prefix}/swagger/?format=openapi')
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        paths = schema.get('paths', {})

        check = [
            ('/carbon-api/mdm/reference-sets/{id}/values/', 'get'),
            ('/carbon-api/mdm/reference-sets/{id}/transition/', 'post'),
            ('/carbon-api/mdm/reference-sets/archive-bulk/', 'post'),
            ('/carbon-api/mdm/org-units/{id}/tree/', 'get'),
            ('/carbon-api/mdm/org-units/{id}/ancestors/', 'get'),
            ('/carbon-api/dq/rules/{id}/execute/', 'post'),
            ('/carbon-api/dq/profile/', 'post'),
            ('/carbon-api/dq/run/', 'post'),
            ('/carbon-api/dq/metrics/', 'get'),
            ('/carbon-api/catalog/assets/archive-bulk/', 'post'),
        ]
        for path, method in check:
            with self.subTest(path=path, method=method):
                op = paths.get(path, {}).get(method, {})
                self.assertTrue(
                    op.get('description', '').strip(),
                    msg=f'{method.upper()} {path} has no description in Swagger schema',
                )
