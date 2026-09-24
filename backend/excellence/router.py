"""Route the ledger to its own database (ADR-0051 §7).

The ``excellence`` alias holds Event, Snapshot and Exemption for every brand.
No model here has a foreign key into a brand table, so cross-database joins
never arise; subjects are referenced by stable id plus commit hash.
"""
from __future__ import annotations

ALIAS = "excellence"
APP_LABEL = "excellence"


class ExcellenceRouter:
    def db_for_read(self, model, **hints):
        return ALIAS if model._meta.app_label == APP_LABEL else None

    def db_for_write(self, model, **hints):
        return ALIAS if model._meta.app_label == APP_LABEL else None

    def allow_relation(self, obj1, obj2, **hints):
        a = obj1._meta.app_label == APP_LABEL
        b = obj2._meta.app_label == APP_LABEL
        if a or b:
            return a and b
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if app_label == APP_LABEL:
            return db == ALIAS
        if db == ALIAS:
            return False
        return None
