"""Exact supported dimensions and decimal arithmetic; no guessed density factors."""

import math
import re
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

from ..errors import invalid

FACTORS = {
    "g": ("g", Decimal(1)),
    "kg": ("g", Decimal(1000)),
    "ml": ("ml", Decimal(1)),
    "l": ("ml", Decimal(1000)),
    "tsp": ("ml", Decimal(5)),
    "tbsp": ("ml", Decimal(15)),
    "pcs": ("pcs", Decimal(1)),
}
UNIT_ALIASES = {
    "g": "g",
    "gram": "g",
    "grams": "g",
    "kg": "kg",
    "kilogram": "kg",
    "kilograms": "kg",
    "ml": "ml",
    "millilitre": "ml",
    "millilitres": "ml",
    "milliliter": "ml",
    "l": "l",
    "litre": "l",
    "litres": "l",
    "liter": "l",
    "liters": "l",
    "tsp": "tsp",
    "teaspoon": "tsp",
    "teaspoons": "tsp",
    "tbsp": "tbsp",
    "tbs": "tbsp",
    "tablespoon": "tbsp",
    "tablespoons": "tbsp",
    "": "pcs",
    "pc": "pcs",
    "pcs": "pcs",
    "piece": "pcs",
    "pieces": "pcs",
    "clove": "pcs",
    "cloves": "pcs",
}


def decimal(value) -> Decimal:
    return Decimal(str(value))


def rounded(value) -> float:
    number = decimal(value)
    if not number.is_finite():
        raise invalid("Quantity must be finite")
    with localcontext() as context:
        context.prec = max(28, len(number.as_tuple().digits) + abs(number.adjusted()) + 4)
        result = float(number.quantize(Decimal(".01"), rounding=ROUND_HALF_UP))
    if not math.isfinite(result):
        raise invalid("Canonical quantity exceeds the supported numeric range")
    return result


def positive_rounded(value) -> float:
    result = rounded(value)
    if result <= 0:
        raise invalid("Quantity must remain positive at canonical precision (0.01)")
    return result


def normalize(quantity, unit: str, canonical: str) -> float:
    dimension, factor = FACTORS.get(unit, (None, None))
    if dimension != canonical:
        raise invalid(f"Unit {unit!r} is not compatible with {canonical}")
    return positive_rounded(decimal(quantity) * factor)


def scale(quantity, servings: int, base: int) -> float:
    # Rounding to zero must never make a nonzero requirement silently free.
    return positive_rounded(decimal(quantity) * servings / base)


def parse_measure(measure: str, canonical: str) -> float:
    """Only fully quantified amounts; reject ranges, cups, pinches, 'to taste', etc."""
    match = re.fullmatch(r"\s*(\d+\s+\d+/\d+|\d+/\d+|\d+(?:\.\d+)?)\s*([a-zA-Z]*)\s*", measure)
    if not match:
        raise invalid(f"Unsupported quantity {measure!r}: no exact conversion")
    amount, raw_unit = match.groups()
    try:
        parts = amount.split()
        if len(parts) == 2:
            amount_value = Fraction(parts[0]) + Fraction(parts[1])
        else:
            amount_value = Fraction(parts[0])
        quantity = Decimal(amount_value.numerator) / Decimal(amount_value.denominator)
    except (ValueError, ZeroDivisionError):
        raise invalid(f"Invalid quantity {measure!r}") from None
    unit = UNIT_ALIASES.get(raw_unit.casefold())
    if unit is None or quantity <= 0:
        raise invalid(f"Unsupported quantity {measure!r}")
    return normalize(quantity, unit, canonical)
