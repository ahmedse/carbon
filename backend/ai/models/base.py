"""Shared base for the AI intelligence durable-state models (Phase 2).

``AppScopeMixin`` is the CBAC partitioning surface shared by all 49 engine
tables. Every durable row is scoped by:

  - ``app_identifier`` — single-tenant namespace (``"carbon"``); always injected.
  - ``org_unit_id``    — org subtree partition, expanded at the query boundary
                         (reusing ``accounts.rbac_utils`` in the caller).
  - ``host_user_id``   — owner identity for ``visibility="private"`` rows.
  - ``visibility``     — ``global | shared | private``, mirroring the engine's
                         ``_apply_tenancy_filter`` semantics exactly.

The ``ai`` package imports NOTHING from accounts/catalog/mdm/dq/emissions/core;
org-subtree expansion happens at the query boundary and is passed into the
Store as a filter parameter.
"""

import uuid

from django.db import models


def generate_uuid() -> str:
    """Return a stringified UUID4 — mirrors ``ai.engine.core.models.generate_uuid``."""
    return str(uuid.uuid4())


class AppScopeMixin(models.Model):
    """CBAC partitioning columns shared by all 49 engine tables.

    Fields mirror R1/R4 of TASKS-PULSE-VENDOR-PHASE-2-KNOWLEDGE.md.
    """

    app_identifier = models.CharField(max_length=64, default="carbon", db_index=True)
    org_unit_id = models.BigIntegerField(null=True, blank=True, db_index=True)
    host_user_id = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    visibility = models.CharField(max_length=16, default="private")

    class Meta:
        abstract = True
