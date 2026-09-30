from __future__ import annotations

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class PasswordComplexityValidator:
    """Light policy: one letter and one digit. Length is MinimumLengthValidator."""

    letter_pattern = re.compile(r"[A-Za-z]")
    digit_pattern = re.compile(r"\d")

    def validate(self, password: str, user=None) -> None:
        if not password:
            raise ValidationError(_('Password cannot be empty.'), code='password_no_value')

        if not self.letter_pattern.search(password):
            raise ValidationError(
                _('Password must contain at least one letter.'),
                code='password_no_letter',
            )
        if not self.digit_pattern.search(password):
            raise ValidationError(
                _('Password must contain at least one digit.'),
                code='password_no_digit',
            )

    def get_help_text(self) -> str:
        return _(
            'Your password must be at least 10 characters and include a letter and a digit.'
        )
