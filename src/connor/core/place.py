import json
import random
import re
import tomllib
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from functools import cache
from importlib.resources import files
from pathlib import Path
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from connor.core.embed import name_text
from connor.core.index import Entry
from connor.core.scan import Folder

PlaceTier = Literal["high", "med", "stays"]
NEIGHBORS = 3
NAME_BONUS = 0.2
EMPTY_FACTOR = 0.9
TYPE_WEIGHT = 0.25
MIN_SAMPLES = 20
SAMPLE_LIMIT = 500
HIGH_PRECISION = 0.95
MED_PRECISION = 0.8
STOPWORDS = frozenset(
    (files("connor") / "data" / "stopwords.txt").read_text(encoding="utf-8").split()
)


@dataclass(frozen=True, slots=True)
class Cutoffs:
    high: float
    high_gap: float
    med: float
    med_gap: float

    def to_text(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_text(cls, text: str) -> "Cutoffs | None":
        try:
            data = json.loads(text)
            return cls(**{key: float(data[key]) for key in cls.__dataclass_fields__})
        except (ValueError, KeyError, TypeError):
            return None


DEFAULT_CUTOFFS = Cutoffs(high=0.45, high_gap=0.15, med=0.3, med_gap=0.03)


@dataclass(frozen=True, slots=True)
class Match:
    folder: Folder
    score: float
    like: Path | None
    hit: str | None


@dataclass(frozen=True, slots=True)
class Placement:
    path: Path
    best: Match | None
    runner_up: Match | None
    tier: PlaceTier


@dataclass(frozen=True, slots=True, eq=False)
class Targets:
    folders: tuple[Folder, ...]
    matrix: NDArray[np.float32]
    paths: tuple[Path, ...]
    owners: NDArray[np.int64]
    rows: tuple[NDArray[np.int64], ...]
    pools: tuple[NDArray[np.int64], ...]
    names: Mapping[str, tuple[tuple[int, float], ...]]
    kinds: tuple[Counter[str], ...]
    counts: tuple[int, ...]
    row_tokens: tuple[frozenset[str], ...]
    row_suffixes: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Calibration:
    cutoffs: Cutoffs
    samples: int
    folders: int
    accuracy: float
    high_share: float
    high_precision: float
    med_share: float
    med_precision: float


def file_tokens(name: str, text: str) -> frozenset[str]:
    """Collect the words that can match folder names.

    Args:
        name: File name as words, from name_text.
        text: Opening text of the file.

    Returns:
        Every word of the name, plus codes like "his210" and versions like
        "2.4.1" from the text. Plain words in the text are left out.
    """
    lowered = text.lower()
    joined = {a + b for a, b in re.findall(r"\b([a-z]{2,5})[ -]?(\d{2,4})\b", lowered)}
    coded = {
        token
        for token in _words(lowered)
        if re.search(r"\d", token) and re.search(r"[a-z.]", token)
    }
    return frozenset(_words(name.lower())) | joined | coded


def _words(text: str) -> list[str]:
    return re.findall(r"\d+(?:\.\d+)+|[^\W_]+", text)


def build_targets(folders: Sequence[Folder], entries: Mapping[Path, Entry]) -> Targets:
    """Prepare the library for scoring.

    Args:
        folders: Candidate folders from the library scan.
        entries: Index entries for the sampled files in those folders.

    Returns:
        Everything place and calibrate need, computed once.
    """
    vectors: list[NDArray[np.float32]] = []
    paths: list[Path] = []
    owners: list[int] = []
    for index, folder in enumerate(folders):
        for path in folder.files:
            found = entries.get(path)
            if found is not None:
                vectors.append(found.vector)
                paths.append(path)
                owners.append(index)
    owner_array = np.array(owners, dtype=np.int64)
    rows = tuple(np.flatnonzero(owner_array == index) for index in range(len(folders)))
    return Targets(
        folders=tuple(folders),
        matrix=np.stack(vectors) if vectors else np.zeros((0, 0), dtype=np.float32),
        paths=tuple(paths),
        owners=owner_array,
        rows=rows,
        pools=_pools(folders, rows),
        names=_name_index(folders),
        kinds=tuple(_kind_counts(folder.files) for folder in folders),
        counts=tuple(len(folder.files) for folder in folders),
        row_tokens=tuple(
            file_tokens(name_text(path), entries[path].text) for path in paths
        ),
        row_suffixes=tuple(path.suffix.lower() for path in paths),
    )


def _pools(
    folders: Sequence[Folder], rows: tuple[NDArray[np.int64], ...]
) -> tuple[NDArray[np.int64], ...]:
    siblings: dict[str, list[int]] = defaultdict(list)
    for index, folder in enumerate(folders):
        siblings[folder.rel.rpartition("/")[0]].append(index)
    pools = []
    for index, folder in enumerate(folders):
        others = [
            rows[i] for i in siblings[folder.rel.rpartition("/")[0]] if i != index
        ]
        pools.append(np.concatenate(others) if others else np.zeros(0, dtype=np.int64))
    return tuple(pools)


def _name_index(folders: Sequence[Folder]) -> dict[str, tuple[tuple[int, float], ...]]:
    nodes: dict[str, set[str]] = defaultdict(set)
    for folder in folders:
        parts = folder.rel.split("/")
        for depth in range(len(parts)):
            node = "/".join(parts[: depth + 1])
            for token in _words(parts[depth].lower()):
                nodes[token].add(node)
    index: dict[str, dict[int, float]] = defaultdict(dict)
    for number, folder in enumerate(folders):
        parts = folder.rel.split("/")
        for depth, part in enumerate(parts):
            weight = 1.0 if depth == len(parts) - 1 else 0.5
            for token in _words(part.lower()):
                if _distinctive(token) and len(nodes[token]) <= 2:
                    index[token][number] = max(index[token].get(number, 0.0), weight)
    return {token: tuple(sorted(found.items())) for token, found in index.items()}


def _distinctive(token: str) -> bool:
    if re.fullmatch(r"\d+(?:\.\d+)+", token):
        return True
    has_digit = bool(re.search(r"\d", token))
    has_letter = bool(re.search(r"[^\W\d_]", token))
    if has_digit and has_letter:
        return len(token) >= 3
    return has_letter and len(token) >= 4 and token not in STOPWORDS


def _kind_counts(paths: Sequence[Path]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for path in paths:
        counts.update(_kinds(path.suffix.lower()))
    return counts


def _kinds(suffix: str) -> list[str]:
    family = family_of(suffix)
    return [suffix, f"type:{family}"] if family else [suffix]


def family_of(suffix: str) -> str | None:
    return _families().get(suffix.lower())


@cache
def _families() -> dict[str, str]:
    data = tomllib.loads(
        (files("connor") / "data" / "types.toml").read_text(encoding="utf-8")
    )
    return {f".{ext}": family for family, exts in data.items() for ext in exts}


def place(
    entries: Sequence[Entry], targets: Targets, cutoffs: Cutoffs
) -> list[Placement]:
    """Pick the best folder for each file.

    Args:
        entries: Index entries for the inbox files.
        targets: The prepared library.
        cutoffs: Score and gap thresholds for the high and med tiers.

    Returns:
        One placement per file, in order.
    """
    if not entries or not targets.folders:
        return [Placement(entry.path, None, None, "stays") for entry in entries]
    queries = np.stack([entry.vector for entry in entries])
    tokens = [file_tokens(name_text(entry.path), entry.text) for entry in entries]
    suffixes = [entry.path.suffix.lower() for entry in entries]
    scores, likes = _score(targets, queries, tokens, suffixes, own=None)
    return [
        _placement(targets, entry.path, scores[i], likes[i], tokens[i], cutoffs)
        for i, entry in enumerate(entries)
    ]


def _score(
    targets: Targets,
    queries: NDArray[np.float32],
    tokens: Sequence[frozenset[str]],
    suffixes: Sequence[str],
    own: Sequence[int] | None,
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    if targets.matrix.size:
        sims = (queries @ targets.matrix.T).astype(np.float64)
    else:
        sims = np.zeros((len(queries), 0))
    if own is not None:
        sims[np.arange(len(own)), list(own)] = -np.inf
    near, likes = _neighbors(sims, targets.rows)
    pool, _ = _neighbors(sims, targets.pools)
    bonus = _name_bonus(targets, tokens)
    empty = np.isnan(near)
    near = np.where(
        empty, np.where(bonus > 0, EMPTY_FACTOR * np.nan_to_num(pool), 0), near
    )
    likes = np.where(empty, -1, likes)
    fit = _type_fit(targets, suffixes, own)
    return near * fit + NAME_BONUS * bonus, likes


def _neighbors(
    sims: NDArray[np.float64], groups: Sequence[NDArray[np.int64]]
) -> tuple[NDArray[np.float64], NDArray[np.int64]]:
    count = sims.shape[0]
    means = np.full((count, len(groups)), np.nan)
    likes = np.full((count, len(groups)), -1, dtype=np.int64)
    for index, rows in enumerate(groups):
        if rows.size == 0:
            continue
        block = sims[:, rows]
        order = np.argsort(-block, axis=1, kind="stable")[:, :NEIGHBORS]
        top = np.take_along_axis(block, order, axis=1)
        finite = np.isfinite(top)
        found = finite.sum(axis=1)
        total = np.where(finite, top, 0.0).sum(axis=1)
        means[:, index] = np.where(found > 0, total / np.maximum(found, 1), np.nan)
        likes[:, index] = np.where(found > 0, rows[order[:, 0]], -1)
    return means, likes


def _name_bonus(
    targets: Targets, tokens: Sequence[frozenset[str]]
) -> NDArray[np.float64]:
    bonus = np.zeros((len(tokens), len(targets.folders)))
    for row, words in enumerate(tokens):
        for word in words:
            for folder, weight in targets.names.get(word, ()):
                bonus[row, folder] = max(bonus[row, folder], weight)
    return bonus


def _type_fit(
    targets: Targets, suffixes: Sequence[str], own: Sequence[int] | None
) -> NDArray[np.float64]:
    fit = np.ones((len(suffixes), len(targets.folders)))
    for row, suffix in enumerate(suffixes):
        kinds = _kinds(suffix)
        own_folder = int(targets.owners[own[row]]) if own is not None else -1
        for folder, counts in enumerate(targets.kinds):
            removed = 1 if folder == own_folder else 0
            exact = counts[kinds[0]] - removed
            family = counts[kinds[1]] - removed if len(kinds) > 1 else exact
            total = targets.counts[folder] - removed
            share = (exact + 0.5 * (family - exact) + 0.5) / (total + 1)
            fit[row, folder] = 1 - TYPE_WEIGHT + TYPE_WEIGHT * share
    return fit


def _placement(
    targets: Targets,
    path: Path,
    scores: NDArray[np.float64],
    likes: NDArray[np.int64],
    tokens: frozenset[str],
    cutoffs: Cutoffs,
) -> Placement:
    order = np.argsort(-scores, kind="stable")
    if scores[order[0]] <= 0:
        return Placement(path, None, None, "stays")
    best = _match(targets, int(order[0]), scores, likes, tokens)
    runner_up = (
        _match(targets, int(order[1]), scores, likes, tokens)
        if len(order) > 1
        else None
    )
    gap = best.score - (runner_up.score if runner_up else 0.0)
    return Placement(path, best, runner_up, _tier(best.score, gap, cutoffs))


def _match(
    targets: Targets,
    folder: int,
    scores: NDArray[np.float64],
    likes: NDArray[np.int64],
    tokens: frozenset[str],
) -> Match:
    hits = sorted(
        (-weight, word)
        for word in tokens
        for number, weight in targets.names.get(word, ())
        if number == folder
    )
    like = int(likes[folder])
    return Match(
        folder=targets.folders[folder],
        score=float(scores[folder]),
        like=targets.paths[like] if like >= 0 else None,
        hit=hits[0][1] if hits else None,
    )


def _tier(score: float, gap: float, cutoffs: Cutoffs) -> PlaceTier:
    if score >= cutoffs.high and gap >= cutoffs.high_gap:
        return "high"
    if score >= cutoffs.med and gap >= cutoffs.med_gap:
        return "med"
    return "stays"


def calibrate(
    targets: Targets, limit: int = SAMPLE_LIMIT, seed: int = 0
) -> Calibration:
    """Measure placement on the library itself and tune the tier cutoffs.

    Each sampled file is hidden from its folder and placed again. Cutoffs are
    chosen so the high tier is right at least HIGH_PRECISION of the time and
    the med tier MED_PRECISION. The reported shares and precisions come from a
    two-fold split, so they are not measured on the data used for tuning.

    Args:
        targets: The prepared library.
        limit: Most files to sample.
        seed: Seed for sampling, so results repeat.

    Returns:
        The cutoffs and how well they did.
    """
    total = len(targets.paths)
    folders = sum(1 for rows in targets.rows if rows.size)
    if total == 0 or folders < 2:
        return Calibration(DEFAULT_CUTOFFS, total, folders, 0.0, 0.0, 0.0, 0.0, 0.0)
    rng = random.Random(seed)
    rows = sorted(rng.sample(range(total), min(limit, total)))
    best, score, gap = _hide_and_place(targets, rows)
    correct = best == targets.owners[rows]
    if len(rows) < MIN_SAMPLES:
        tiers = _tiers(score, gap, DEFAULT_CUTOFFS)
        return _report(DEFAULT_CUTOFFS, len(rows), folders, correct, tiers)
    shuffled = list(range(len(rows)))
    rng.shuffle(shuffled)
    halves = (np.array(shuffled[::2]), np.array(shuffled[1::2]))
    tiers = np.empty(len(rows), dtype=object)
    for train, test in (halves, halves[::-1]):
        fitted = _fit(score[train], gap[train], correct[train])
        tiers[test] = _tiers(score[test], gap[test], fitted)
    return _report(_fit(score, gap, correct), len(rows), folders, correct, tiers)


def _hide_and_place(
    targets: Targets, rows: list[int]
) -> tuple[NDArray[np.int64], NDArray[np.float64], NDArray[np.float64]]:
    tokens = [targets.row_tokens[row] for row in rows]
    suffixes = [targets.row_suffixes[row] for row in rows]
    scores, _ = _score(targets, targets.matrix[rows], tokens, suffixes, own=rows)
    order = np.argsort(-scores, axis=1, kind="stable")
    first = np.take_along_axis(scores, order[:, :1], axis=1)[:, 0]
    second = np.take_along_axis(scores, order[:, 1:2], axis=1)[:, 0]
    return order[:, 0], first, first - second


def _fit(
    score: NDArray[np.float64], gap: NDArray[np.float64], correct: NDArray[np.bool_]
) -> Cutoffs:
    high, high_gap = _choose(score, gap, correct, HIGH_PRECISION)
    med, med_gap = _choose(score, gap, correct, MED_PRECISION)
    return Cutoffs(high=high, high_gap=high_gap, med=med, med_gap=med_gap)


def _choose(
    score: NDArray[np.float64],
    gap: NDArray[np.float64],
    correct: NDArray[np.bool_],
    precision: float,
) -> tuple[float, float]:
    support = max(3, int(0.05 * len(score)))
    best, covered = (float("inf"), float("inf")), 0
    for low in np.unique(np.quantile(score, np.linspace(0, 0.95, 20))):
        for margin in np.unique(
            np.quantile(gap, np.linspace(0, 0.9, 10), method="lower")
        ):
            chosen = (score >= low) & (gap >= margin)
            count = int(chosen.sum())
            if (
                count >= support
                and count > covered
                and correct[chosen].mean() >= precision
            ):
                best, covered = (float(low), float(margin)), count
    return best


def _tiers(
    score: NDArray[np.float64], gap: NDArray[np.float64], cutoffs: Cutoffs
) -> NDArray[np.object_]:
    return np.array(
        [_tier(float(s), float(g), cutoffs) for s, g in zip(score, gap, strict=True)],
        dtype=object,
    )


def _report(
    cutoffs: Cutoffs,
    samples: int,
    folders: int,
    correct: NDArray[np.bool_],
    tiers: NDArray[np.object_],
) -> Calibration:
    def share(tier: str) -> float:
        return float(np.mean(tiers == tier))

    def precision(tier: str) -> float:
        chosen = tiers == tier
        return float(correct[chosen].mean()) if chosen.any() else 0.0

    return Calibration(
        cutoffs=cutoffs,
        samples=samples,
        folders=folders,
        accuracy=float(correct.mean()),
        high_share=share("high"),
        high_precision=precision("high"),
        med_share=share("med"),
        med_precision=precision("med"),
    )
