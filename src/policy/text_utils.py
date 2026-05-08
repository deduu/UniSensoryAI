"""Small text helpers for policy review heuristics."""

from __future__ import annotations

import re

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9_-]*")

ALLOW_TERMS = {"may", "can", "allowed", "permitted", "allow", "permit"}
DENY_TERMS = {
    "must not",
    "shall not",
    "may not",
    "cannot",
    "prohibited",
    "forbidden",
    "ban",
    "banned",
    "deny",
}
REQUIRE_TERMS = {"must", "shall", "required", "require", "mandatory"}

COMMON_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "the",
    "their",
    "this",
    "that",
    "these",
    "those",
    "to",
    "with",
    "within",
}

DOMAIN_FILLER_STOPWORDS = {
    "company",
    "document",
    "documents",
    "employee",
    "employees",
    "existing",
    "new",
    "organization",
    "organizations",
    "place",
    "policy",
    "policies",
    "regulation",
    "regulations",
    "section",
    "team",
    "teams",
    "university",
    "use",
    "used",
    "using",
    "user",
    "users",
}

QUERY_FILLER_STOPWORDS = DOMAIN_FILLER_STOPWORDS | {
    "allow",
    "allowed",
    "allowing",
    "can",
    "cannot",
    "forbidden",
    "mandatory",
    "may",
    "must",
    "not",
    "permit",
    "permitted",
    "prohibited",
    "require",
    "required",
    "shall",
    "unless",
    "without",
}

IMPORTANT_SHORT_TOKENS = {
    "ai",
    "gdpr",
    "ferpa",
    "hipaa",
    "hr",
    "it",
    "pci",
    "phi",
    "pii",
    "ssn",
}


def split_clauses(text: str) -> list[str]:
    """Split extracted policy text into reviewable clauses."""
    clauses = [part.strip(" \t\r\n-") for part in _SENTENCE_SPLIT_RE.split(text)]
    return [clause for clause in clauses if len(clause) >= 12]


def token_set(text: str) -> set[str]:
    """Return normalized content-ish tokens for overlap checks."""
    stopwords = COMMON_STOPWORDS | DOMAIN_FILLER_STOPWORDS
    return {word.lower() for word in _WORD_RE.findall(text) if word.lower() not in stopwords}


def shared_content_tokens(left: str, right: str) -> set[str]:
    """Return overlapping normalized content tokens for two clauses."""
    return token_set(left) & token_set(right)


def keywords_for_query(text: str, *, max_terms: int = 8) -> list[str]:
    """Extract stable keyword terms from a clause for web search."""
    seen: set[str] = set()
    terms: list[str] = []
    for word in _WORD_RE.findall(text):
        normalized = word.lower()
        if normalized in COMMON_STOPWORDS or normalized in QUERY_FILLER_STOPWORDS:
            continue
        if normalized in seen:
            continue
        if len(normalized) < 4 and normalized not in IMPORTANT_SHORT_TOKENS:
            continue
        terms.append(normalized)
        seen.add(normalized)
        if len(terms) >= max_terms:
            break
    return terms


def has_any(text: str, terms: set[str]) -> bool:
    """Return whether any normalized term is present."""
    normalized = text.lower()
    return any(term in normalized for term in terms)


def policy_stance(text: str) -> str:
    """Classify a clause's rough policy stance."""
    if has_any(text, DENY_TERMS):
        return "deny"
    if has_any(text, ALLOW_TERMS):
        return "allow"
    if has_any(text, REQUIRE_TERMS):
        return "require"
    return "neutral"


def overlap_score(left: str, right: str) -> float:
    """Compute simple Jaccard overlap for two clauses."""
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0
    return len(left_tokens & right_tokens) / len(left_tokens | right_tokens)
