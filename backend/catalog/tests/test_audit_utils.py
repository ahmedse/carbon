"""Regression tests for ``catalog.audit_utils.emit_governance_event``.

Guards the Fix-2 landmine: a governance-event insert that raises (e.g. a
PostgreSQL ``DataError`` from an over-long ``entity_type``/``action``) MUST be
isolated in its own savepoint so it can never poison — and roll back — the
caller's business transaction.
"""

import pytest
from django.db import transaction

from catalog.audit_utils import emit_governance_event
from catalog.models import GlossaryTerm, GovernanceEvent


@pytest.mark.django_db
def test_governance_event_failure_does_not_roll_back_caller_write(create_user):
    """A DataError on the event insert must NOT discard the caller's write."""
    user = create_user('audit_isolated')

    with transaction.atomic():
        # The business write the caller actually cares about.
        term = GlossaryTerm.objects.create(term='Isolation Proof', definition='survives')

        # Force a DataError on the event insert: entity_type is varchar(40),
        # so a 50-char value fails at the database level.
        emit_governance_event(
            entity_type='X' * 50,
            entity_id=1,
            action='create',
            before=None,
            after={},
            user=user,
        )

    # The failed event insert was rolled back (isolated)…
    assert not GovernanceEvent.objects.filter(entity_type='X' * 50).exists()

    # …but the caller's business write survived.
    assert GlossaryTerm.objects.filter(pk=term.pk).exists()
