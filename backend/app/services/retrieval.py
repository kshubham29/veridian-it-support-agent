"""Keyword + category scoring retrieval over the company knowledge base.

Deliberately simple (no vector DB) - the corpus is 11 short policies, so a
transparent lexical scorer is more explainable and faster to demo.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from .store import store

_WORD = re.compile(r"[a-z0-9']+")


def tokenize(text: str) -> List[str]:
    return _WORD.findall(text.lower())


def score_article(article: dict, message: str) -> float:
    msg = message.lower()
    tokens = set(tokenize(message))
    score = 0.0
    for kw in article.get("keywords", []):
        kw_l = kw.lower()
        if " " in kw_l:
            if kw_l in msg:
                score += 3.0
        elif kw_l in tokens:
            score += 2.0
    for word in tokenize(article["title"]):
        if word in tokens:
            score += 1.5
    body_tokens = set(tokenize(article["text"]))
    overlap = tokens & body_tokens
    score += 0.2 * len(overlap)
    return score


def search(message: str, top_k: int = 3) -> List[Tuple[dict, float]]:
    scored = [(a, score_article(a, message)) for a in store.knowledge_base]
    scored = [s for s in scored if s[1] > 0]
    scored.sort(key=lambda s: s[1], reverse=True)
    return scored[:top_k]


def search_ids(message: str, top_k: int = 3) -> List[str]:
    return [a["id"] for a, _ in search(message, top_k)]


def by_category(category: str) -> List[dict]:
    return [a for a in store.knowledge_base if a["category"] == category]


def keyword_filter(query: str) -> List[dict]:
    """Used by the Knowledge Base page search box."""
    if not query.strip():
        return store.knowledge_base
    q = query.lower()
    return [
        a
        for a in store.knowledge_base
        if q in a["id"].lower()
        or q in a["title"].lower()
        or q in a["text"].lower()
        or any(q in kw.lower() for kw in a.get("keywords", []))
    ]


def precedents(category: str, limit: int = 3) -> List[dict]:
    """Closed tickets in the same category - used as context/precedent only."""
    return [
        t
        for t in store.tickets
        if t["category"] == category and not t.get("is_active", True)
    ][:limit]
