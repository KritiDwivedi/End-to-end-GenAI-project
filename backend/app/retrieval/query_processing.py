from __future__ import annotations

import re

from pydantic import BaseModel


class ProcessedQuery(BaseModel):
    original_query: str
    keyword_terms: list[str]
    sparse_query: str


# These words describe the question rather than the filing passage we want.
STOP_WORDS = {
    "a",
    "about",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "can",
    "did",
    "do",
    "does",
    "for",
    "from",
    "give",
    "has",
    "have",
    "how",
    "i",
    "in",
    "is",
    "it",
    "me",
    "of",
    "on",
    "please",
    "say",
    "show",
    "tell",
    "that",
    "the",
    "their",
    "them",
    "this",
    "to",
    "what",
    "was",
    "were",
    "which",
    "who",
    "with",
    "would",
    "you",
}

GENERIC_WORDS = {
    "amount",
    "answer",
    "company",
    "document",
    "filing",
    "fiscal",
    "identify",
    "information",
    "reported",
    "report",
    "statement",
    "total",
    "year",
}

DOMAIN_TERMS = {
    "assets",
    "cash",
    "cybersecurity",
    "debt",
    "employees",
    "expenses",
    "income",
    "liabilities",
    "margin",
    "revenue",
    "sales",
    "risks",
    "retention",
    "operating",
    "research",
    "development",
}

TOKEN_PATTERN = re.compile(r"[A-Za-z]+(?:[-'][A-Za-z]+)*|\d{4}|\d+(?:\.\d+)?%?")


def _clean_token(token: str) -> str:
    token = token.strip("'-").lower()
    if token.endswith("'s"):
        token = token[:-2]
    return token


def extract_keyword_terms(query: str, *, limit: int = 5) -> list[str]:
    """Extract stable lexical terms without making another model/API call."""
    candidates: list[tuple[str, int, int]] = []
    seen: set[str] = set()

    for position, raw_token in enumerate(TOKEN_PATTERN.findall(query)):
        token = _clean_token(raw_token)
        if not token or token in STOP_WORDS or token in GENERIC_WORDS:
            continue
        if len(token) < 3 and not token.isdigit():
            continue
        if token in seen:
            continue
        seen.add(token)

        score = 0
        if token in DOMAIN_TERMS:
            score += 4
        if re.fullmatch(r"(?:19|20)\d{2}", token):
            score += 5
        if token.isdigit() or token.endswith("%"):
            score += 3
        if len(token) >= 7:
            score += 1
        candidates.append((token, score, position))

    # Preserve the query's natural order after selecting the most useful terms.
    selected = sorted(candidates, key=lambda item: (-item[1], item[2]))[:limit]
    return [token for token, _, _ in sorted(selected, key=lambda item: item[2])]


def process_query(query: str, *, limit: int = 5) -> ProcessedQuery:
    terms = extract_keyword_terms(query, limit=limit)
    sparse_query = " OR ".join(terms) if terms else query
    return ProcessedQuery(
        original_query=query,
        keyword_terms=terms,
        sparse_query=sparse_query,
    )
