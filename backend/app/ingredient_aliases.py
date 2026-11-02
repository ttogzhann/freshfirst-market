"""Deterministic normalization and ambiguity-safe ingredient alias matching."""

import difflib
import unicodedata
from dataclasses import dataclass


def normalize_alias(value: str) -> str:
    """Normalize human/source text without changing its meaning."""
    value = unicodedata.normalize("NFKC", value).casefold()
    chars = []
    for char in value:
        category = unicodedata.category(char)
        chars.append(" " if category.startswith("P") else char)
    return " ".join("".join(chars).split())


def normalization_variants(value: str) -> tuple[str, ...]:
    normalized = normalize_alias(value)
    variants = [normalized]
    # Russian users commonly omit ё. Only add this equivalent after the exact
    # spelling is considered; the resolver still refuses conflicting results.
    folded = normalized.replace("ё", "е")
    if folded != normalized:
        variants.append(folded)
    return tuple(variants)


@dataclass(frozen=True)
class AliasMatch:
    status: str
    ingredient_ids: tuple[str, ...] = ()
    suggestion: str | None = None
    confidence: float | None = None
    requires_confirmation: bool = False


def resolve_rows(rows, value: str) -> AliasMatch:
    rows = list(rows)
    normalized = normalize_alias(value)
    exact_rows = [row for row in rows if row["normalized_text"] in normalization_variants(value)]
    candidates = {}
    for row in exact_rows:
        candidates.setdefault(row["ingredient_id"], row["alias_text"])
    ids = tuple(sorted(candidates))
    if len(ids) == 1:
        return AliasMatch("exact", ids)
    if len(ids) > 1:
        return AliasMatch("ambiguous", ids)
    best = []
    for row in rows:
        score = difflib.SequenceMatcher(None, normalized, row["normalized_text"]).ratio()
        if score >= 0.86:
            best.append((score, row))
    best.sort(key=lambda item: (-item[0], item[1]["normalized_text"], item[1]["ingredient_id"]))
    if best and (len(best) == 1 or best[0][0] > best[1][0] + 0.04):
        score, row = best[0]
        return AliasMatch(
            "suggestion",
            (row["ingredient_id"],),
            row["alias_text"],
            round(score, 3),
            True,
        )
    return AliasMatch("unresolved")
