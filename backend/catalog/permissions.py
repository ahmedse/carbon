# catalog/permissions.py
# Canonical definitions have moved to accounts.permissions.
# Re-export for backward compatibility.

from accounts.permissions import ReadAnyWriteAdmin, AdminOrSuperuserOnly

__all__ = ['ReadAnyWriteAdmin', 'AdminOrSuperuserOnly']
