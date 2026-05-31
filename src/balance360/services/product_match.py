"""
Fuzzy matching of free-text invoice-line descriptions to catalog products.

Pure functions: they receive the product list, so they're trivial to unit
test and don't couple to the DB session. The caller loads products once and
passes them in.

Scorer: token_set_ratio. Product descriptions from suppliers carry extra spec
tokens in varying order ("HD 12TB SEAGATE IRONWOLF SATA 6GB/S 256MB NAS"), so
a token-set scorer (which compares the *set* of words, ignoring order and
duplicates) ranks far better than ratio/WRatio, which can be fooled by shared
substrings.
"""
from __future__ import annotations
from dataclasses import dataclass
from rapidfuzz import process, fuzz

from balance360.models.product import Product

# Score (0-100) at or above which a match is linked automatically, no prompt.
AUTO_ACCEPT_SCORE = 90
# Below this, the match is too weak to even suggest.
SUGGEST_MIN_SCORE = 30


@dataclass
class ProductSuggestion:
    product: Product
    score: int


def suggest(description: str, products: list[Product], limit: int = 5) -> list[ProductSuggestion]:
    """Return the best-matching products for a description, best first."""
    if not description or not products:
        return []
    names = [p.name for p in products]
    matches = process.extract(description, names, scorer=fuzz.token_set_ratio, limit=limit)
    return [
        ProductSuggestion(product=products[idx], score=round(score))
        for _, score, idx in matches
        if score >= SUGGEST_MIN_SCORE
    ]


def best_match(description: str, products: list[Product]) -> ProductSuggestion | None:
    """Single best suggestion, or None if nothing clears SUGGEST_MIN_SCORE."""
    top = suggest(description, products, limit=1)
    return top[0] if top else None
