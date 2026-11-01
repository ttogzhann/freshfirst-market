"""Strict, provider-neutral account identifier normalization."""

from email_validator import EmailNotValidError, validate_email


def normalize_email(value):
    if not isinstance(value, str):
        raise ValueError("email must be valid")
    if len(value) > 254:
        raise ValueError("email must be valid")
    email = value.strip()
    if not email:
        raise ValueError("email must be valid")
    try:
        validate_email(email, check_deliverability=False, allow_smtputf8=False)
    except EmailNotValidError:
        raise ValueError("email must be valid") from None
    return email, email.casefold()
