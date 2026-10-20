"""Startup configuration shared with injected service validation."""

import re


def expiry_days(value=None):
    if value is None:
        return 3
    if isinstance(value, str) and re.fullmatch(r"[0-9]+", value):
        value = int(value)
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not 0 <= value <= 9007199254740991
        or value != int(value)
    ):
        raise ValueError(
            "FRESHFIRST_EXPIRY_DAYS must be a nonnegative whole-day integer "
            "(maximum 9007199254740991)."
        )
    return int(value)
