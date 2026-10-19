import os
import re
import shutil
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

import numpy as np
from numpy.typing import NDArray

from connor.errors import ModelError

if TYPE_CHECKING:
    from model2vec import StaticModel

NAME_WEIGHT = 0.5
MODEL_FILES = ["*.json", "*.safetensors", "*.md"]


class Embedder(Protocol):
    """Turn texts into unit-length vectors."""

    @property
    def model_id(self) -> str: ...

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]: ...


def name_text(path: Path) -> str:
    tokens = re.findall(r"\d+(?:\.\d+)+|[^\W_]+", path.stem)
    return " ".join(_split_camel(token) for token in tokens)


def _split_camel(token: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", token)


def file_vectors(
    embedder: Embedder, items: Sequence[tuple[str, str]]
) -> NDArray[np.float32]:
    """Embed files from their name and their text.

    Args:
        embedder: Model that turns text into vectors.
        items: One (name text, body text) pair per file.

    Returns:
        One unit-length row per file. The name and body vectors are blended by
        NAME_WEIGHT. Files with no body use the name vector alone.
    """
    if not items:
        return np.zeros((0, 0), dtype=np.float32)
    vectors = embedder.encode([name for name, _ in items]).astype(np.float32)
    with_body = [index for index, (_, body) in enumerate(items) if body.strip()]
    if with_body:
        bodies = embedder.encode([items[index][1] for index in with_body])
        vectors[with_body] = (
            NAME_WEIGHT * vectors[with_body] + (1 - NAME_WEIGHT) * bodies
        )
    return _normalize(vectors)


def _normalize(vectors: NDArray[np.float32]) -> NDArray[np.float32]:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    unit: NDArray[np.float32] = (vectors / norms).astype(np.float32)
    return unit


def model_dir(name: str, cache: Path) -> Path:
    local = Path(name).expanduser()
    if local.is_dir():
        return local
    return cache / "models" / name.replace("/", "--")


class StaticEmbedder:
    def __init__(self, model_id: str, model: "StaticModel") -> None:
        self._model_id = model_id
        self._model = model

    @property
    def model_id(self) -> str:
        return self._model_id

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        vectors = self._model.encode(
            list(texts), show_progress_bar=False, use_multiprocessing=False
        )
        return _normalize(np.asarray(vectors, dtype=np.float32))


def load_embedder(name: str, cache: Path) -> StaticEmbedder:
    """Load the embedding model from disk.

    Args:
        name: Hugging Face model name or a local folder.
        cache: Cache dir that holds downloaded models.

    Returns:
        The loaded model. It never touches the network.

    Raises:
        ModelError: The model is not on disk yet.
    """
    directory = model_dir(name, cache)
    if not any(directory.glob("*.safetensors")):
        raise ModelError(f"model {name} is not downloaded yet")
    from model2vec import StaticModel

    return StaticEmbedder(name, StaticModel.from_pretrained(directory))


def download_model(name: str, cache: Path) -> Path:
    """Download the embedding model once.

    Args:
        name: Hugging Face model name.
        cache: Cache dir that holds downloaded models.

    Returns:
        The folder the model was saved to.

    Raises:
        ModelError: The download failed or holds no model weights.
    """
    target = model_dir(name, cache)
    partial = target.with_name(target.name + ".part")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
    os.environ["HF_HUB_VERBOSITY"] = "error"
    import huggingface_hub

    shutil.rmtree(partial, ignore_errors=True)
    try:
        huggingface_hub.snapshot_download(
            repo_id=name, local_dir=partial, allow_patterns=MODEL_FILES, token=False
        )
    except Exception as error:
        shutil.rmtree(partial, ignore_errors=True)
        raise ModelError(f"could not download model {name}: {error}") from None
    shutil.rmtree(partial / ".cache", ignore_errors=True)
    if not any(partial.glob("*.safetensors")):
        shutil.rmtree(partial, ignore_errors=True)
        raise ModelError(f"model {name} has no model weights. Check [model] name")
    shutil.rmtree(target, ignore_errors=True)
    partial.replace(target)
    return target
