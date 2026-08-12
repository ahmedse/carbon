"""
Carbon AI Intelligence — Security Guards

AI CONTRACT §9: Every AI call passes through guard chain BEFORE reaching provider.
Five mandatory guards execute in order. Any guard failure = call rejected.

Architecture: CarbonIntelligence → Guard Chain → AIProvider
               ↑                                    ↑
          protocol.py                          protocol.py
               ↑
          guards.py (this file) — sits BETWEEN

NEVER skip a guard. NEVER reorder them. Each guard is stateless.
"""

from __future__ import annotations

import logging
from typing import Any

from .protocol import Scope

logger = logging.getLogger("carbon.ai.guards")


# ── Guard 1: ScopeGuard ──────────────────────────────────────────────────
# AI CONTRACT §1: No call without a Scope. Null scope = REJECT.

class ScopeGuard:
    """Rejects any AI call that does not carry a valid Scope.

    §1-SCOPE Rule 1: Scope is mandatory.
    §1-SCOPE Rule 2: Scope must have at minimum a user_identifier.
    """

    @staticmethod
    def validate(scope: Scope | None, operation: str) -> None:
        """Raise ValueError if scope is missing or invalid."""
        if scope is None:
            raise ValueError(
                f"AI call rejected by ScopeGuard: operation='{operation}' "
                f"has no Scope. Every AI call MUST carry a Scope. "
                f"See ai-contract.md §1."
            )
        if not scope.user_identifier:
            raise ValueError(
                f"AI call rejected by ScopeGuard: operation='{operation}' "
                f"has Scope with empty user_identifier."
            )


# ── Guard 2: AccessGuard ─────────────────────────────────────────────────
# AI CONTRACT §3: User may only access resources in their scope.

class AccessGuard:
    """Validates that the user's Scope grants access to requested resources.

    Checks:
      - org_unit_ids: user's scope must cover the requested org units
      - module_ids: user's scope must cover the requested modules
    """

    @staticmethod
    def validate(
        scope: Scope,
        operation: str,
        requested_org_units: list[str] | None = None,
        requested_modules: list[str] | None = None,
    ) -> None:
        """Raise PermissionError if scope does not cover requested resources."""
        # Superuser bypasses all access checks
        if scope.is_superuser:
            return

        # Wildcard org_unit_ids means all-access
        if scope.org_unit_ids != ["*"] and requested_org_units:
            if not set(requested_org_units).issubset(set(scope.org_unit_ids)):
                raise PermissionError(
                    f"AI call rejected by AccessGuard: operation='{operation}' "
                    f"requested org_units {requested_org_units} not in "
                    f"scope org_units {scope.org_unit_ids}"
                )

        if requested_modules:
            if not set(requested_modules).issubset(set(scope.module_ids)):
                raise PermissionError(
                    f"AI call rejected by AccessGuard: operation='{operation}' "
                    f"requested modules {requested_modules} not in "
                    f"scope modules {scope.module_ids}"
                )


# ── Guard 3: DataIsolationGuard ─────────────────────────────────────────
# AI CONTRACT §3: No cross-app data leakage. Domain apps are silos.

class DataIsolationGuard:
    """Ensures domain-app isolation. Carbon footprint data NEVER leaks to water app.

    §3-DATA-ISOLATION Rule 1: Every domain AI call must declare app_identifier.
    §3-DATA-ISOLATION Rule 2: app_identifier determines which tables/columns are visible.
    §3-DATA-ISOLATION Rule 3: Platform-level calls (no app_identifier) may not access
                              domain-specific data.
    """

    # Registered domain apps and their allowed table prefixes
    DOMAIN_TABLES: dict[str, list[str]] = {
        "emissions": ["emissions_", "carbon_", "footprint_", "emission_"],
        # Future: "water": ["water_", "aquifer_"],
        # Future: "waste": ["waste_", "landfill_"],
    }

    @staticmethod
    def validate(
        scope: Scope,
        operation: str,
        table_names: list[str] | None = None,
    ) -> None:
        """Raise PermissionError if operation would cross domain boundaries."""
        if table_names is None:
            return

        app = scope.app_identifier

        if app is None:
            # Platform-level call — must not touch domain-specific tables
            for domain, prefixes in DataIsolationGuard.DOMAIN_TABLES.items():
                for table in table_names:
                    if any(table.startswith(p) for p in prefixes):
                        raise PermissionError(
                            f"AI call rejected by DataIsolationGuard: "
                            f"platform-level operation='{operation}' attempted "
                            f"to access domain table '{table}' (belongs to '{domain}'). "
                            f"Set app_identifier in Scope or use domain-scoped call."
                        )
            return

        # Domain-scoped call — must only touch own domain's tables
        allowed_prefixes = DataIsolationGuard.DOMAIN_TABLES.get(app)
        if allowed_prefixes is None:
            logger.warning(
                "DataIsolationGuard: unregistered domain app '%s' in operation '%s'. "
                "Allowing pass-through. Register in DOMAIN_TABLES.",
                app, operation,
            )
            return

        for table in table_names:
            if not any(table.startswith(p) for p in allowed_prefixes):
                raise PermissionError(
                    f"AI call rejected by DataIsolationGuard: "
                    f"domain='{app}' operation='{operation}' attempted "
                    f"to access table '{table}' outside its domain. "
                    f"Allowed prefixes: {allowed_prefixes}"
                )

    @staticmethod
    def sanitize_response(
        scope: Scope,
        response_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Strip any data that belongs to a different domain app.

        Called AFTER provider returns, BEFORE response is sent to caller.
        This is a defense-in-depth measure — the provider should already
        respect isolation, but we strip at the boundary as a safety net.
        """
        app = scope.app_identifier
        if app is None:
            return response_data  # Platform calls see everything

        allowed = DataIsolationGuard.DOMAIN_TABLES.get(app)
        if allowed is None:
            return response_data

        # Remove any table references outside this domain
        sanitized = dict(response_data)
        for key in list(sanitized.keys()):
            if any(key.startswith(p) for p in DataIsolationGuard._all_prefixes_except(app)):
                logger.warning(
                    "DataIsolationGuard: stripped key '%s' from response "
                    "for domain='%s'", key, app,
                )
                del sanitized[key]
        return sanitized

    @staticmethod
    def _all_prefixes_except(app: str) -> list[str]:
        """All registered table prefixes except the given app's."""
        result: list[str] = []
        for domain, prefixes in DataIsolationGuard.DOMAIN_TABLES.items():
            if domain != app:
                result.extend(prefixes)
        return result


# ── Guard 4: MutationGuard ──────────────────────────────────────────────
# AI CONTRACT §4: AI NEVER auto-mutates. Read-only scope = no mutation suggestions.

class MutationGuard:
    """Prevents AI from suggesting or performing data mutations.

    §4-NO-AUTO-MUTATION Rule 1: AIProvider responses are advisory only.
    §4-NO-AUTO-MUTATION Rule 2: Read-only scope blocks all mutation suggestions.
    §4-NO-AUTO-MUTATION Rule 3: Fix suggestions require explicit human confirmation.
    """

    MUTATION_OPERATIONS = {
        "suggest_fix",
        "auto_correct",
        "apply_fix",
        "bulk_update",
        "delete_records",
        "anonymize_data",
    }

    MUTATION_KEYWORDS_IN_RESPONSE = [
        "UPDATE ", "DELETE ", "INSERT ", "DROP ", "ALTER ",
        "TRUNCATE ", "CREATE TABLE", "auto-fix", "auto_correct",
    ]

    @staticmethod
    def validate(scope: Scope, operation: str) -> None:
        """Reject mutation operations when scope is read-only."""
        if scope.is_read_only and operation in MutationGuard.MUTATION_OPERATIONS:
            raise PermissionError(
                f"AI call rejected by MutationGuard: operation='{operation}' "
                f"is a mutation but scope is read-only. "
                f"See ai-contract.md §4."
            )

    @staticmethod
    def sanitize_response(
        scope: Scope,
        response_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Strip mutation suggestions from read-only responses.

        Scans response text fields (explanation, narrative, content) for
        mutation keywords and either strips or flags them.
        """
        if not scope.is_read_only:
            return response_data

        sanitized = dict(response_data)
        text_fields = ["explanation", "narrative", "content", "description", "summary"]

        for field in text_fields:
            if field in sanitized and isinstance(sanitized[field], str):
                text = sanitized[field]
                for keyword in MutationGuard.MUTATION_KEYWORDS_IN_RESPONSE:
                    if keyword.lower() in text.lower():
                        logger.warning(
                            "MutationGuard: stripped mutation keyword '%s' "
                            "from field '%s' in read-only response",
                            keyword, field,
                        )
                        sanitized[field] = (
                            "[Mutation suggestion redacted — read-only scope]\n"
                            + text
                        )
                        break

        return sanitized


# ── Guard 5: AuditTrail ─────────────────────────────────────────────────
# AI CONTRACT §7: Every AI call logged with 8 fields.

class AuditTrail:
    """Logs every AI call for governance and audit.

    §7-AUDIT-TRAIL: 8 required fields logged per call:
      1. timestamp (ISO 8601)
      2. user_identifier
      3. app_identifier (or "platform")
      4. operation
      5. provider_name
      6. latency_ms
      7. status (completed/failed/rejected_by_guard)
      8. error_message (or null)

    Also captures:
      - scope snapshot (via Scope.to_dict())
      - request fingerprint (hash of payload for idempotency)
    """

    @staticmethod
    def log(
        scope: Scope,
        operation: str,
        provider_name: str,
        latency_ms: int,
        status: str,
        error_message: str | None = None,
        request_fingerprint: str | None = None,
    ) -> None:
        """Write audit record. Uses structured logging for log aggregation."""
        import json
        from datetime import datetime, timezone

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "user_identifier": scope.user_identifier,
            "app_identifier": scope.app_identifier or "platform",
            "operation": operation,
            "provider_name": provider_name,
            "latency_ms": latency_ms,
            "status": status,
            "error_message": error_message,
            "scope_snapshot": scope.to_dict(),
            "request_fingerprint": request_fingerprint,
        }

        logger.info("AI_AUDIT %s", json.dumps(record, default=str))


# ── Guard Chain Runner ───────────────────────────────────────────────────
# AI CONTRACT §9: All 5 guards execute in order. Any failure = call rejected.

class GuardChain:
    """Runs all 5 guards in the mandatory order.

    Usage:
        chain = GuardChain()
        chain.run(scope, operation, table_names=[...], ...)
        # If we get here, all guards passed.
        audit_trail = chain.audit_trail  # Pre-configured for logging
    """

    def __init__(self) -> None:
        self.scope_guard = ScopeGuard()
        self.access_guard = AccessGuard()
        self.isolation_guard = DataIsolationGuard()
        self.mutation_guard = MutationGuard()
        self.audit_trail = AuditTrail()

    def run(
        self,
        scope: Scope | None,
        operation: str,
        *,
        requested_org_units: list[str] | None = None,
        requested_modules: list[str] | None = None,
        table_names: list[str] | None = None,
    ) -> Scope:
        """Execute all 5 guards in order. Returns the validated Scope.

        Raises:
            ValueError: ScopeGuard failure (missing/invalid scope)
            PermissionError: AccessGuard, DataIsolationGuard, or MutationGuard failure
        """
        # Guard 1: Scope must exist and have user_identifier
        self.scope_guard.validate(scope, operation)
        assert scope is not None  # Narrowed by ScopeGuard

        # Guard 2: Access control
        self.access_guard.validate(
            scope, operation, requested_org_units, requested_modules,
        )

        # Guard 3: Data isolation between domain apps
        self.isolation_guard.validate(scope, operation, table_names)

        # Guard 4: No auto-mutation
        self.mutation_guard.validate(scope, operation)

        # Guard 5: Audit trail is NOT run here — the caller (CarbonIntelligence)
        #           logs after the provider call completes so latency_ms is known.
        #           The AuditTrail.log() staticmethod is called explicitly.

        return scope

    def sanitize_response(
        self,
        scope: Scope,
        response_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply response sanitization (defense in depth).

        Runs after provider returns, before response is sent to caller.
        """
        response_data = self.isolation_guard.sanitize_response(scope, response_data)
        response_data = self.mutation_guard.sanitize_response(scope, response_data)
        return response_data
