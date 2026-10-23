"""Conservative exact normalized comparisons without fuzzy identity inference."""

import re
import unicodedata


def normalized_text(value: str) -> str:
    """Normalize Unicode, case, punctuation and whitespace for complete-name checks."""
    text = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def contains_text(quote: str, value: str) -> bool:
    """Check complete normalized words; never accept an empty or partial token."""
    needle = normalized_text(value)
    return bool(needle) and f" {needle} " in f" {normalized_text(quote)} "
