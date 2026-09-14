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


class RefreshRateThrottle(AnonRateThrottle):
    """Per-IP cap on JWT refresh.

    Refresh is a legitimate recurring operation (the frontend refreshes every
    ~10 min plus on tab focus), so it gets its own generous scope instead of
    sharing the aggressive 'anon' bucket. A shared-IP dev box or a burst of
    anonymous requests would otherwise 429 the refresh and force a spurious
    logout (the frontend treats a 401/400 as "session expired", so a 429 here
    must not be conflated with a dead token).
    """
    scope = 'refresh'
