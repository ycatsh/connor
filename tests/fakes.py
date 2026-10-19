import re
import zlib
from collections.abc import Sequence

import numpy as np
from numpy.typing import NDArray

DIMENSIONS = 256


class FakeEmbedder:
    def __init__(self, model_id: str = "fake") -> None:
        self.model_id = model_id
        self.calls = 0
        self.texts: list[str] = []

    def encode(self, texts: Sequence[str]) -> NDArray[np.float32]:
        self.calls += 1
        self.texts.extend(texts)
        vectors = np.zeros((len(texts), DIMENSIONS), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                vectors[row, zlib.crc32(word.encode()) % DIMENSIONS] += 1.0
        norms = np.linalg.norm(vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vectors / norms
