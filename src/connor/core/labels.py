import re
from collections.abc import Mapping, Sequence
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from connor.config.schema import Category
from connor.core.embed import Embedder, name_text
from connor.core.index import Entry
from connor.core.place import Match, Placement, PlaceTier
from connor.core.scan import Folder

SEED_SHARE = 0.3
NAME_BONUS = 0.25
HIGH_GAP = 0.12
MED_GAP = 0.05
FLOOR = 0.2


def place_by_labels(
    entries: Sequence[Entry],
    labels: Sequence[Category],
    folders: Sequence[Folder],
    existing: Mapping[Path, Entry],
    embedder: Embedder,
) -> list[Placement]:
    """Place files into folders named after the given labels.

    Each label starts from its own text. Files already in its folder and the
    clearest inbox matches are blended in, then every file is scored again.

    Args:
        entries: Inbox files.
        labels: Label names and optional descriptions.
        folders: One folder per label, in the same order.
        existing: Index entries for files already in those folders.
        embedder: Model used to embed the label text.

    Returns:
        One placement per inbox file. Tiers come from the gap between the best
        and second best label.
    """
    if not entries:
        return []
    queries = np.stack([entry.vector for entry in entries])
    base = embedder.encode([f"{label.name} {label.description}" for label in labels])
    members = [
        [existing[path] for path in folder.files if path in existing]
        for folder in folders
    ]
    bonus = np.zeros((len(entries), len(labels)), dtype=np.float32)
    hits = [_hit(entry, labels) for entry in entries]
    for row, label in enumerate(hits):
        if label is not None:
            bonus[row, label] = NAME_BONUS
    first = queries @ _prototypes(base, members, []).T + bonus
    scores = queries @ _prototypes(base, members, _seeds(first, entries)).T + bonus
    return [
        _placement(entry, scores[row], folders, members, hits[row], labels)
        for row, entry in enumerate(entries)
    ]


def _prototypes(
    base: NDArray[np.float32],
    members: list[list[Entry]],
    seeds: list[list[Entry]],
) -> NDArray[np.float32]:
    rows = []
    for index, vector in enumerate(base):
        known = members[index] + (seeds[index] if seeds else [])
        blended = (
            vector + np.mean([e.vector for e in known], axis=0) if known else vector
        )
        norm = float(np.linalg.norm(blended)) or 1.0
        rows.append(blended / norm)
    return np.stack(rows).astype(np.float32)


def _seeds(scores: NDArray[np.float32], entries: Sequence[Entry]) -> list[list[Entry]]:
    order = np.argsort(-scores, axis=1, kind="stable")
    best = order[:, 0]
    top = np.take_along_axis(scores, order[:, :1], axis=1)[:, 0]
    second = np.take_along_axis(scores, order[:, 1:2], axis=1)[:, 0]
    clear = (top >= FLOOR) & (top - second >= MED_GAP)
    seeds: list[list[Entry]] = [[] for _ in range(scores.shape[1])]
    for label in range(scores.shape[1]):
        rows = [row for row in range(len(entries)) if best[row] == label and clear[row]]
        rows.sort(key=lambda row: -float(scores[row, label]))
        keep = max(1, int(len(rows) * SEED_SHARE)) if rows else 0
        seeds[label] = [entries[row] for row in rows[:keep]]
    return seeds


def _hit(entry: Entry, labels: Sequence[Category]) -> int | None:
    words = {
        _singular(word) for word in re.findall(r"[a-z]+", name_text(entry.path).lower())
    }
    for index, label in enumerate(labels):
        if _singular(label.name.lower()) in words:
            return index
    return None


def _singular(word: str) -> str:
    return word[:-1] if word.endswith("s") and len(word) > 3 else word


def _placement(
    entry: Entry,
    scores: NDArray[np.float32],
    folders: Sequence[Folder],
    members: list[list[Entry]],
    hit: int | None,
    labels: Sequence[Category],
) -> Placement:
    order = np.argsort(-scores, kind="stable")
    best = int(order[0])
    gap = float(scores[best] - (scores[order[1]] if len(order) > 1 else 0.0))
    match = Match(
        folder=folders[best],
        score=float(scores[best]),
        like=_closest(entry, members[best]),
        hit=labels[best].name.lower() if hit == best else None,
    )
    return Placement(entry.path, match, None, _tier(float(scores[best]), gap))


def _closest(entry: Entry, members: list[Entry]) -> Path | None:
    if not members:
        return None
    sims = [float(entry.vector @ member.vector) for member in members]
    return members[int(np.argmax(sims))].path


def _tier(score: float, gap: float) -> PlaceTier:
    if score < FLOOR:
        return "stays"
    if gap >= HIGH_GAP:
        return "high"
    return "med" if gap >= MED_GAP else "stays"
