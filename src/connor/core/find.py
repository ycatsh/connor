import math
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from connor.core.embed import Embedder, name_text
from connor.core.index import Entry
from connor.core.place import STOPWORDS

FUSION = 60
POOL = 50
SNIPPET = 80


@dataclass(frozen=True, slots=True)
class Hit:
    path: Path
    score: float
    snippet: str


def search(
    query: str, entries: Sequence[Entry], embedder: Embedder, limit: int
) -> list[Hit]:
    """Find files by words and by meaning.

    Keyword and vector rankings are merged with reciprocal rank fusion, so a
    file that ranks well both ways comes first.

    Args:
        query: What to look for.
        entries: Index entries to search.
        embedder: Model used to embed the query.
        limit: Most hits to return.

    Returns:
        The best hits, each with the line that matches the query best.
    """
    if not entries:
        return []
    terms = _tokens(query)
    documents = [_tokens(f"{name_text(e.path)} {e.title} {e.text}") for e in entries]
    keyword = np.array(_bm25(terms, documents))
    meaning = (
        np.stack([entry.vector for entry in entries]) @ embedder.encode([query])[0]
    )
    fused: dict[int, float] = defaultdict(float)
    for ranked in (_ranked(keyword, matches_only=True), _ranked(meaning)):
        for rank, index in enumerate(ranked[:POOL]):
            fused[index] += 1 / (FUSION + rank + 1)
    order = sorted(fused, key=lambda index: (-fused[index], str(entries[index].path)))
    return [
        Hit(
            entries[index].path, round(fused[index], 6), _snippet(entries[index], terms)
        )
        for index in order[:limit]
    ]


def _tokens(text: str) -> list[str]:
    words = re.findall(r"\d+(?:\.\d+)+|[^\W_]+", text.lower())
    return [word for word in words if word not in STOPWORDS]


def _bm25(terms: list[str], documents: list[list[str]]) -> list[float]:
    count = len(documents)
    average = sum(len(document) for document in documents) / count or 1.0
    spread = Counter(term for document in documents for term in set(document))
    scores = []
    for document in documents:
        frequency = Counter(document)
        score = 0.0
        for term in set(terms):
            if not frequency[term]:
                continue
            weight = math.log(1 + (count - spread[term] + 0.5) / (spread[term] + 0.5))
            norm = frequency[term] + 1.5 * (0.25 + 0.75 * len(document) / average)
            score += weight * frequency[term] * 2.5 / norm
        scores.append(score)
    return scores


def _ranked(scores: NDArray[np.float64], matches_only: bool = False) -> list[int]:
    order = [int(index) for index in np.argsort(-scores, kind="stable")]
    return [index for index in order if scores[index] > 0] if matches_only else order


def _snippet(entry: Entry, terms: list[str]) -> str:
    wanted = set(terms)
    lines = [line for line in entry.text.splitlines() if line.strip()]
    if not lines:
        return entry.title[:SNIPPET]
    _, best = max(
        enumerate(lines),
        key=lambda item: (len(wanted & set(_tokens(item[1]))), -item[0]),
    )
    return best[:SNIPPET]
