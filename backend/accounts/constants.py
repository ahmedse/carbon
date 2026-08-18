# accounts/constants.py
# Single source of truth for RBAC group names, role sets, and protected groups.
# Import from this module everywhere — never hardcode group name strings.

# ── Canonical group names ──────────────────────────────────────────
# These are the Django auth_group.name values used across the platform.
ADMINS_GROUP = "admins_group"
DATAOWNERS_GROUP = "dataowners_group"
ANALYSTS_GROUP = "analysts_group"
VIEWERS_GROUP = "viewers_group"
AUDITORS_GROUP = "auditors_group"
CARBON_DATA_OWNERS_GROUP = "carbon_data_owners_group"
CARBON_ANALYSTS_GROUP = "carbon_analysts_group"

# Alias for backward compatibility — "admin" is the bare Django group
ADMIN_GROUP = "admin"

# ── Domain Lead roles (org-scoped, app-specific administration) ───
# Pattern: {app}_lead → grants "{app}-admin" perspective within org scope.
# Domain Leads manage their app's domain data/config — NOT platform users/roles/orgs.
# Platform administration remains reserved for global admins_group (org_unit=None).
CARBON_LEAD_GROUP = "carbon_lead"
CATALOG_LEAD_GROUP = "catalog_lead"
MDM_LEAD_GROUP = "mdm_lead"
DQ_LEAD_GROUP = "dq_lead"
DATAHUB_LEAD_GROUP = "datahub_lead"
TURNKEY_LEAD_GROUP = "turnkey_lead"

DOMAIN_LEAD_GROUPS = {CARBON_LEAD_GROUP, CATALOG_LEAD_GROUP, MDM_LEAD_GROUP, DQ_LEAD_GROUP, DATAHUB_LEAD_GROUP, TURNKEY_LEAD_GROUP}

# ── Role classification sets ───────────────────────────────────────
# Roles that confer full platform administration (global only).
ADMIN_ROLES = {ADMIN_GROUP, ADMINS_GROUP}

# Roles whose holders may VIEW (but not necessarily write) emissions/module data.
# ScopedRole with any of these grants READ visibility to modules/orgs in scope.
VISIBILITY_ROLES = {
    ADMINS_GROUP,
    DATAOWNERS_GROUP,
    AUDITORS_GROUP,
    VIEWERS_GROUP,
    ANALYSTS_GROUP,
    *DOMAIN_LEAD_GROUPS,
}

# Roles that are READ-ONLY — holders of ONLY these roles cannot create/update/delete.
# Note: a user who holds BOTH a read-only role AND a write role (e.g. dataowners_group)
# is NOT blocked; this set is used to deny write when the user's ONLY qualifying role
# is read-only.
READ_ONLY_ROLES = {VIEWERS_GROUP, ANALYSTS_GROUP}

# ── Protected groups (cannot be deleted via the GroupViewSet) ──────
PROTECTED_GROUPS = {
    ADMIN_GROUP,
    ADMINS_GROUP,
    CARBON_DATA_OWNERS_GROUP,
    CARBON_ANALYSTS_GROUP,
    CARBON_LEAD_GROUP,
    CATALOG_LEAD_GROUP,
    MDM_LEAD_GROUP,
    DQ_LEAD_GROUP,
    DATAHUB_LEAD_GROUP,
    TURNKEY_LEAD_GROUP,
}

# ── Convenience: all canonical group names as a flat set ───────────
ALL_CANONICAL_GROUPS = {
    ADMINS_GROUP,
    DATAOWNERS_GROUP,
    ANALYSTS_GROUP,
    VIEWERS_GROUP,
    AUDITORS_GROUP,
    CARBON_DATA_OWNERS_GROUP,
    CARBON_ANALYSTS_GROUP,
    *DOMAIN_LEAD_GROUPS,
}
