"""Single-process, serialized transactions; copy-on-write rollback, no persistence."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from threading import RLock

from .models import BasketItem, CookingRecord, PantryItem, Recipe, ShoppingItem


@dataclass
class State:
    pantry: dict[str, PantryItem] = field(default_factory=dict)
    recipes: dict[str, Recipe] = field(default_factory=dict)
    basket: dict[str, BasketItem] = field(default_factory=dict)
    shopping: dict[str, ShoppingItem] = field(default_factory=dict)
    history: list[CookingRecord] = field(default_factory=list)
    removed_generated: bool = False
    seq: int = 0


class MemoryStore:
    def __init__(self):
        self.state = State()
        self.lock = RLock()

    def next_id(self, prefix: str) -> str:
        self.state.seq += 1
        return f"{prefix}_{self.state.seq}"

    @contextmanager
    def transaction(self):
        with self.lock:
            previous = deepcopy(self.state)
            try:
                yield self.state
            except Exception:
                self.state = previous
                raise
