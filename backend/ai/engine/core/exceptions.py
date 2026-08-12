"""
Custom exception hierarchy for Pulse.
All application-level errors inherit from PulseError.
"""


class PulseError(Exception):
    """Base exception for all Pulse errors."""

    def __init__(self, detail: str = "An error occurred", status_code: int = 500):
        self.detail = detail
        self.status_code = status_code
        super().__init__(self.detail)


class HostConnectionError(PulseError):
    """Cannot connect to the host database."""

    def __init__(self, detail: str = "Failed to connect to host database"):
        super().__init__(detail=detail, status_code=503)


class IntrospectionError(PulseError):
    """Schema introspection failed."""

    def __init__(self, detail: str = "Schema introspection failed"):
        super().__init__(detail=detail, status_code=500)


class LLMError(PulseError):
    """LLM call failed."""

    def __init__(self, detail: str = "LLM request failed"):
        super().__init__(detail=detail, status_code=502)


class ToolExecutionError(PulseError):
    """Tool execution failed."""

    def __init__(self, detail: str = "Tool execution failed"):
        super().__init__(detail=detail, status_code=500)
