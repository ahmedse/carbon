"""P1-11 — Cross-tenant isolation at the engine store query boundary.

The DjangoStore no longer carries a misleading ``_apply_tenancy_filter`` no-op:
tenancy (``instance_id`` + ``visibility`` triplet) is enforced by ``scope_q()``,
which callers inject into ``select``/``execute`` filters. These tests prove a
cross-tenant read returns zero rows for each of the three memory stores
(episodic, long-term, insight).
"""

import pytest
from django.utils import timezone

from ai.models.core import Insight, MemoryEpisodic, MemoryLongTerm
from ai.store import scope_q

TENANT_A = "tenant-a"
TENANT_B = "tenant-b"


@pytest.mark.django_db
def test_scope_q_cross_tenant_returns_zero_rows():
    # Tenant A owns one visible row in each of the three memory stores.
    MemoryEpisodic.objects.create(
        instance_id=TENANT_A,
        event_type="task_done",
        summary="tenant A episode",
        visibility="global",
        occurred_at=timezone.now(),
    )
    MemoryLongTerm.objects.create(
        instance_id=TENANT_A,
        category="policy",
        content="tenant A long-term memory",
        visibility="shared",
    )
    Insight.objects.create(
        instance_id=TENANT_A,
        insight_type="trend",
        title="tenant A insight",
        content="tenant A insight body",
        visibility="shared",
    )

    # A different tenant must see ZERO rows from tenant A, for every store.
    for model in (MemoryEpisodic, MemoryLongTerm, Insight):
        rows = model.objects.filter(scope_q(model, TENANT_B, "user-b"))
        assert rows.count() == 0, f"{model.__name__} leaked rows across tenants"


@pytest.mark.django_db
def test_scope_q_same_tenant_returns_own_rows():
    MemoryEpisodic.objects.create(
        instance_id=TENANT_A,
        event_type="task_done",
        summary="tenant A episode",
        visibility="shared",
        occurred_at=timezone.now(),
    )
    MemoryLongTerm.objects.create(
        instance_id=TENANT_A,
        category="policy",
        content="tenant A long-term memory",
        visibility="shared",
    )
    Insight.objects.create(
        instance_id=TENANT_A,
        insight_type="trend",
        title="tenant A insight",
        content="tenant A insight body",
        visibility="shared",
    )

    assert MemoryEpisodic.objects.filter(scope_q(MemoryEpisodic, TENANT_A, "user-b")).count() == 1
    assert MemoryLongTerm.objects.filter(scope_q(MemoryLongTerm, TENANT_A, "user-b")).count() == 1
    assert Insight.objects.filter(scope_q(Insight, TENANT_A, "user-b")).count() == 1


@pytest.mark.django_db
def test_scope_q_private_rows_only_for_owner():
    MemoryLongTerm.objects.create(
        instance_id=TENANT_A,
        category="policy",
        content="owner's private memory",
        visibility="private",
        host_user_id="owner-a",
    )

    # The owner sees their private row.
    assert MemoryLongTerm.objects.filter(
        scope_q(MemoryLongTerm, TENANT_A, "owner-a")
    ).count() == 1
    # Another user in the SAME tenant does not see the private row.
    assert MemoryLongTerm.objects.filter(
        scope_q(MemoryLongTerm, TENANT_A, "other-user")
    ).count() == 0
