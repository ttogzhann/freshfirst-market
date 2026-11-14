"""Deterministic, non-mutating FEFO allocation over pantry lots."""

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from .quantities import decimal


@dataclass(frozen=True)
class LotAllocation:
    lot_id: str
    expiry_date: date
    quantity: Decimal


@dataclass(frozen=True)
class Allocation:
    required: Decimal
    available: Decimal
    allocated: Decimal
    missing: Decimal
    sufficient: bool
    lots: tuple[LotAllocation, ...]


def allocate(lots, ingredient_id, dimension, required, today) -> Allocation:
    required = decimal(required)
    eligible = sorted(
        (
            lot
            for lot in lots
            if lot.ingredient_id == ingredient_id
            and lot.canonical_dimension == dimension
            and lot.resolution_status == "resolved"
            and lot.expiry_date >= today
            and decimal(lot.quantity) > 0
        ),
        key=lambda lot: (lot.expiry_date, lot.id),
    )
    available = sum((decimal(lot.quantity) for lot in eligible), Decimal(0))
    remaining = required
    allocations = []
    for lot in eligible:
        if remaining <= 0:
            break
        quantity = min(decimal(lot.quantity), remaining)
        allocations.append(LotAllocation(lot.id, lot.expiry_date, quantity))
        remaining -= quantity
    allocated = required - remaining
    return Allocation(
        required=required,
        available=available,
        allocated=allocated,
        missing=max(Decimal(0), required - allocated),
        sufficient=remaining == 0,
        lots=tuple(allocations),
    )
