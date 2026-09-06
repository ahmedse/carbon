"""Public service facade for the e-Office Correspondence engine."""

from .registry import allocate_reference_no
from .policies import PolicyNotFound, resolve_policy, freeze_policy

__all__ = ['allocate_reference_no', 'PolicyNotFound', 'resolve_policy', 'freeze_policy']
