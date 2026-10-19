import math
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

from connor.core.embed import name_text
from connor.core.index import Entry
from connor.core.place import STOPWORDS, family_of

GROUP_SIMILARITY = 0.28
ROUNDS = 10
PREFIX_SHARE = 0.6
NAME_WORDS = 2


@dataclass(frozen=True, slots=True)
class Group:
    name: str
    entries: tuple[Entry, ...]


def group_leftovers(
    entries: Sequence[Entry], separator: str, taken: set[str]
) -> list[Group]:
    """Group files that fit no folder, and name each group.

    Args:
        entries: Files left over after placement.
        separator: Joins the words of a group name.
        taken: Folder names already in use, compared without case.

    Returns:
        Groups of two or more files, sorted by name. Files with text group by
        similarity. Files without text group by file type.
    """
    ordered = sorted(entries, key=lambda entry: entry.path.name.lower())
    texted = [entry for entry in ordered if entry.text.strip()]
    clusters = [cluster for cluster in _similar(texted) if len(cluster) >= 2]
    named = list(zip(_names(clusters, separator), clusters, strict=True))
    named += _by_type([entry for entry in ordered if not entry.text.strip()])
    used = {name.casefold() for name in taken}
    groups = []
    for name, members in sorted(named, key=lambda item: item[0].lower()):
        unique = _unique(name, used, separator)
        used.add(unique.casefold())
        groups.append(Group(unique, tuple(members)))
    return groups


def _similar(entries: list[Entry]) -> list[list[Entry]]:
    if not entries:
        return []
    vectors = np.stack([entry.vector for entry in entries])
    labels = np.full(len(entries), -1)
    centroids = np.zeros((0, vectors.shape[1]), dtype=vectors.dtype)
    for _ in range(ROUNDS):
        assigned, centroids = _assign(vectors, centroids)
        if np.array_equal(assigned, labels):
            break
        labels = assigned
    groups: dict[int, list[Entry]] = defaultdict(list)
    for entry, label in zip(entries, labels, strict=True):
        groups[int(label)].append(entry)
    return list(groups.values())


def _assign(
    vectors: np.ndarray, centroids: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    centers = list(centroids)
    labels = np.empty(len(vectors), dtype=np.int64)
    for row, vector in enumerate(vectors):
        if centers:
            sims = np.stack(centers) @ vector
            best = int(np.argmax(sims))
            if sims[best] >= GROUP_SIMILARITY:
                labels[row] = best
                continue
        centers.append(vector.copy())
        labels[row] = len(centers) - 1
    kept = [k for k in range(len(centers)) if np.any(labels == k)]
    remap = {old: new for new, old in enumerate(kept)}
    labels = np.array([remap[int(label)] for label in labels], dtype=np.int64)
    means = np.stack([vectors[labels == k].mean(axis=0) for k in range(len(kept))])
    norms = np.linalg.norm(means, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return labels, means / norms


def _names(clusters: list[list[Entry]], separator: str) -> list[str]:
    counts = [_token_counts(cluster) for cluster in clusters]
    spread = Counter(token for count in counts for token in count)
    names = []
    for cluster, count in zip(clusters, counts, strict=True):
        prefix = _prefix(cluster)
        if prefix:
            names.append(_title(prefix))
            continue
        coverage = _coverage(cluster)
        scores = {
            token: total * coverage[token] * math.log(1 + len(clusters) / spread[token])
            for token, total in count.items()
        }
        best = sorted(scores, key=lambda token: (-scores[token], token))[:NAME_WORDS]
        names.append(separator.join(_title(token) for token in best) or "Group")
    return names


def _token_counts(cluster: list[Entry]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for entry in cluster:
        for word in _words(name_text(entry.path)):
            counts[word] += 2
        counts.update(_words(entry.text))
    return counts


def _words(text: str) -> list[str]:
    return [
        word
        for word in re.findall(r"[^\W\d_]{3,}", text.lower())
        if word not in STOPWORDS
    ]


def _coverage(cluster: list[Entry]) -> dict[str, float]:
    present: Counter[str] = Counter()
    for entry in cluster:
        present.update(set(_words(name_text(entry.path))) | set(_words(entry.text)))
    return {token: count / len(cluster) for token, count in present.items()}


def _prefix(cluster: list[Entry]) -> str | None:
    firsts = []
    for entry in cluster:
        words = _words(name_text(entry.path))
        firsts.append(words[0] if words else "")
    word, count = Counter(firsts).most_common(1)[0]
    return word if word and count / len(cluster) >= PREFIX_SHARE else None


def _title(word: str) -> str:
    return word[:1].upper() + word[1:]


def _by_type(entries: list[Entry]) -> list[tuple[str, list[Entry]]]:
    families: dict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        family = family_of(entry.path.suffix)
        if family:
            families[family].append(entry)
    return [(name, members) for name, members in families.items() if len(members) >= 2]


def _unique(name: str, used: set[str], separator: str) -> str:
    if name.casefold() not in used:
        return name
    count = 2
    while f"{name}{separator}{count}".casefold() in used:
        count += 1
    return f"{name}{separator}{count}"
