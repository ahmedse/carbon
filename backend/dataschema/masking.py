"""Column-level data masking service (EPH-4B)."""
import hashlib


class MaskingService:
    """Deterministic value masking per DataField.masking_strategy."""

    @staticmethod
    def mask_value(value, strategy):
        if value is None:
            return value
        if strategy == 'redact':
            return '[REDACTED]'
        if strategy == 'hash':
            return 'h:' + hashlib.sha256(str(value).encode('utf-8')).hexdigest()[:12]
        if strategy == 'truncate':
            s = str(value)
            return (s[:3] + '***') if len(s) >= 3 else '***'
        if strategy == 'null':
            return None
        # 'none' and unknown strategies fail safe to redaction
        return '[REDACTED]'
