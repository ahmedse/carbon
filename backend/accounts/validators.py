from __future__ import annotations

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class PasswordComplexityValidator:
    """Ensure passwords include upper, lower, digit, and special characters."""

    uppercase_pattern = re.compile(r"[A-Z]")
    lowercase_pattern = re.compile(r"[a-z]")
    digit_pattern = re.compile(r"\d")
    special_pattern = re.compile(r"[!@#$%^&*(),.?\":{}|<>]")

    def validate(self, password: str, user=None) -> None:
        if not password:
            raise ValidationError(_('Password cannot be empty.'), code='password_no_value')

        if not self.uppercase_pattern.search(password):
            raise ValidationError(
                _('Password must contain at least one uppercase letter.'),
                code='password_no_upper',
            )
        if not self.lowercase_pattern.search(password):
            raise ValidationError(
                _('Password must contain at least one lowercase letter.'),
                code='password_no_lower',
            )
        if not self.digit_pattern.search(password):
            raise ValidationError(
                _('Password must contain at least one digit.'),
                code='password_no_digit',
            )
        if not self.special_pattern.search(password):
            raise ValidationError(
                _('Password must contain at least one special character.'),
                code='password_no_special',
            )

    def get_help_text(self) -> str:
        return _(
            'Your password must contain at least 12 characters and include '
            'uppercase, lowercase, numeric, and special characters.'
        )
