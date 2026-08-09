"""
Thin HTTP client for Pulse AI/RAG system.

Zero AI logic. Zero Django ORM imports. Pure HTTP.
Reads PULSE_URL and PULSE_API_KEY from Django settings.
"""

import logging
import uuid
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Public API ──────────────────────────────────────────────────────────


class PulseGateway:
    """Thin HTTP client for Pulse. No AI logic lives here.

    Usage:
        gateway = PulseGateway()
        result = gateway.validate_dq_rules(rules=[...], rows=[...])
    """

    def __init__(self):
        self.base_url = settings.PULSE_URL.rstrip('/')
        self.api_key = settings.PULSE_API_KEY
        self.default_timeout = 10  # seconds — sync DQ calls
        self._agent_card = None

    # ── dq.validate ─────────────────────────────────────────────────────

    def validate_dq_rules(self, rules: list, rows: list, context: dict = None) -> dict:
        """Submit dq.validate task. Returns full response dict.

        Graceful degradation: on timeout/connection-error, returns
        {'status': 'pulse_unavailable', 'error': {...}}.
        """
        task_id = str(uuid.uuid4())
        payload = self._build_dq_validate_payload(task_id, rules, rows, context)

        try:
            resp = requests.post(
                f'{self.base_url}/tasks',
                json=payload,
                timeout=self.default_timeout,
                headers={'Content-Type': 'application/json'},
            )
            resp.raise_for_status()
            return resp.json()

        except requests.Timeout:
            logger.warning(
                'Pulse timeout after %ds for task %s',
                self.default_timeout, task_id,
            )
            return {
                'status': 'pulse_unavailable',
                'error': {
                    'code': 'timeout',
                    'message': f'Pulse request timed out after {self.default_timeout}s',
                },
            }

        except requests.ConnectionError as exc:
            logger.warning(
                'Pulse unreachable at %s: %s',
                self.base_url, exc,
            )
            return {
                'status': 'pulse_unavailable',
                'error': {
                    'code': 'unreachable',
                    'message': f'Pulse at {self.base_url} is unreachable',
                },
            }

        except requests.RequestException as exc:
            logger.error('Pulse request failed for task %s: %s', task_id, exc)
            return {
                'status': 'pulse_unavailable',
                'error': {
                    'code': 'request_failed',
                    'message': str(exc),
                },
            }

        except Exception as exc:
            logger.error('Unexpected Pulse error for task %s: %s', task_id, exc)
            return {
                'status': 'pulse_unavailable',
                'error': {
                    'code': 'unexpected',
                    'message': str(exc),
                },
            }

    # ── Payload Construction ─────────────────────────────────────────────

    def _build_dq_validate_payload(self, task_id: str, rules: list, rows: list, context: dict = None) -> dict:
        """Build the full task envelope matching PULSE_CONTRACT_SPEC.md §1.1 and §3.1.

        rules: list of dicts with keys id, prompt, fields, severity
        rows: list of row-value dicts
        context: optional dict with table_name, row_count_hint, etc.
        """
        mapped_rules = []
        for rule in rules:
            mapped_rules.append({
                'id': str(rule.get('id', '')),
                'prompt': rule.get('prompt', ''),
                'fields': rule.get('fields', []),
                'severity': rule.get('severity', 'error'),
            })

        return {
            'auth': {
                'instance_id': 'carbon',
                'api_key': self.api_key,
            },
            'task': {
                'id': task_id,
                'type': 'dq.validate',
                'payload': {
                    'rules': mapped_rules,
                    'rows': rows,
                    'context': context or {},
                },
                'meta': {},
            },
        }
