# File: connections/services.py
# Service layer for the connections app (Facade pattern).
# Views call these services; services return plain data (payload dicts +
# status codes), never DRF Response objects. Zero behavioral change vs. the
# logic previously in views.

class ConnectionService:
    """Data source connectivity tests and consuming-connection key rotation."""

    @staticmethod
    def test_connection(source):
        """
        Test connectivity of a data source. Returns (payload_dict, status_code)
        so the view can build the Response without duplicating logic.
        """
        try:
            # Placeholder: actual connectivity test would be implemented per source_type
            if not source.connection_config:
                return (
                    {'status': 'failure', 'message': 'No connection config'},
                    400,
                )

            # Simulate a test; real implementation would try actual connection
            source.last_test_status = 'Connection test successful'
            source.status = 'active'
            source.save(update_fields=['last_test_status', 'status', 'last_tested_at'])

            return (
                {
                    'status': 'success',
                    'message': 'Connection test successful',
                    'last_tested_at': source.last_tested_at,
                },
                200,
            )
        except Exception as e:
            source.last_test_status = str(e)
            source.status = 'error'
            source.save(update_fields=['last_test_status', 'status', 'last_tested_at'])
            return (
                {'status': 'failure', 'message': str(e)},
                400,
            )

    @staticmethod
    def rotate_key(connection):
        """
        Generate a new API key for a consuming connection.
        Returns the payload dict (the key is shown once, never again).
        """
        plaintext_key = connection.generate_api_key()
        return {
            'id': connection.id,
            'name': connection.name,
            'api_key': plaintext_key,
            'message': 'API key rotated. Store it safely—it will not be shown again.',
        }
