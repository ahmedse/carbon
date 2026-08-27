"""Custom DRF throttle classes for the Carbon Data Trust Platform (EPH-5B)."""

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class UserMinuteRateThrottle(UserRateThrottle):
    """Per-user per-minute cap (complements the per-hour user cap)."""
    scope = 'user_minute'


class AnonMinuteRateThrottle(AnonRateThrottle):
    """Per-IP per-minute cap for anonymous traffic (complements per-hour anon cap)."""
    scope = 'anon_minute'


class AIRateThrottle(UserRateThrottle):
    """Per-user cap on AI generation endpoints (complement to the in-app RateLimiter)."""
    scope = 'ai'


class HeavyRateThrottle(UserRateThrottle):
    """Per-user cap on heavy import/export endpoints."""
    scope = 'heavy'
