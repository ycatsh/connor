import socket
from pathlib import Path

import numpy as np
import pytest

from connor.core.embed import (
    NAME_WEIGHT,
    download_model,
    file_vectors,
    load_embedder,
    model_dir,
    name_text,
)
from connor.errors import ModelError
from fakes import FakeEmbedder


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("2026-09-01_BIO101_Lab1.pdf", "2026 09 01 BIO101 Lab1"),
        ("LabReportFinal.docx", "Lab Report Final"),
        ("report_(d4).pdf", "report d4"),
        ("plugin-2.4.1+1.21.jar", "plugin 2.4.1 1.21"),
        ("notes.tar.gz", "notes tar"),
        ("README", "README"),
        ("my  file   name.txt", "my file name"),
        ("HTMLParser.py", "HTML Parser"),
    ],
)
def test_name_text(name: str, expected: str) -> None:
    assert name_text(Path(name)) == expected


def test_file_vectors_are_unit_length_and_mix_name_and_text() -> None:
    embedder = FakeEmbedder()

    vectors = file_vectors(
        embedder, [("lab report", "light and pondweed"), ("lab report", "")]
    )

    assert vectors.shape == (2, 256)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
    name_only = embedder.encode(["lab report"])[0]
    assert np.allclose(vectors[1], name_only)
    text_only = embedder.encode(["light and pondweed"])[0]
    mixed = NAME_WEIGHT * name_only + (1 - NAME_WEIGHT) * text_only
    assert np.allclose(vectors[0], mixed / np.linalg.norm(mixed))


def test_file_vectors_handles_no_files() -> None:
    assert file_vectors(FakeEmbedder(), []).shape[0] == 0


def test_model_dir_for_a_hub_name_and_a_local_path(tmp_path: Path) -> None:
    assert model_dir("minishlab/potion-base-8M", tmp_path) == (
        tmp_path / "models" / "minishlab--potion-base-8M"
    )
    local = tmp_path / "my-model"
    local.mkdir()
    assert model_dir(str(local), tmp_path) == local


def test_missing_model_is_an_error_and_never_touches_the_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network used")

    monkeypatch.setattr(socket, "socket", refuse)

    with pytest.raises(ModelError, match="not downloaded"):
        load_embedder("minishlab/potion-base-8M", tmp_path)


def test_loads_a_saved_model_from_disk_without_network(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from model2vec import StaticModel
    from tokenizers import Tokenizer
    from tokenizers.models import WordLevel
    from tokenizers.pre_tokenizers import Whitespace

    vocab = {"[UNK]": 0, "lab": 1, "report": 2, "invoice": 3}
    tokenizer = Tokenizer(WordLevel(vocab, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = Whitespace()
    vectors = np.eye(4, 8, dtype=np.float32)
    target = model_dir("acme/tiny", tmp_path)
    StaticModel(vectors=vectors, tokenizer=tokenizer).save_pretrained(target)

    def refuse(*args: object, **kwargs: object) -> None:
        raise AssertionError("network used")

    monkeypatch.setattr(socket, "socket", refuse)
    embedder = load_embedder("acme/tiny", tmp_path)
    encoded = embedder.encode(["lab report", "invoice"])

    assert embedder.model_id == "acme/tiny"
    assert encoded.shape == (2, 8)
    assert np.allclose(np.linalg.norm(encoded, axis=1), 1.0)
    assert float(encoded[0] @ encoded[1]) == pytest.approx(0.0)


def test_download_runs_for_real_with_only_the_network_faked(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import os

    import huggingface_hub

    calls: list[dict[str, object]] = []

    def fake_snapshot(**kwargs: object) -> str:
        calls.append(kwargs)
        assert os.environ.get("HF_HUB_DISABLE_TELEMETRY") == "1"
        assert os.environ.get("HF_HUB_DISABLE_PROGRESS_BARS") == "1"
        assert os.environ.get("HF_HUB_VERBOSITY") == "error"
        folder = Path(str(kwargs["local_dir"]))
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "model.safetensors").write_bytes(b"weights")
        (folder / "config.json").write_text("{}")
        (folder / ".cache").mkdir()
        return str(folder)

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot)

    target = download_model("minishlab/potion-base-8M", tmp_path)

    assert target == tmp_path / "models" / "minishlab--potion-base-8M"
    assert sorted(p.name for p in target.iterdir()) == [
        "config.json",
        "model.safetensors",
    ]
    assert calls[0]["repo_id"] == "minishlab/potion-base-8M"
    assert calls[0]["token"] is False
    assert not (tmp_path / "models" / "minishlab--potion-base-8M.part").exists()


def test_a_failed_download_leaves_nothing_behind(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import huggingface_hub

    def broken(**kwargs: object) -> str:
        folder = Path(str(kwargs["local_dir"]))
        folder.mkdir(parents=True)
        (folder / "half.safetensors").write_bytes(b"x")
        raise OSError("connection reset")

    monkeypatch.setattr(huggingface_hub, "snapshot_download", broken)

    expected = r"could not download model .*connection reset"
    with pytest.raises(ModelError, match=expected):
        download_model("minishlab/potion-base-8M", tmp_path)

    assert list((tmp_path / "models").iterdir()) == []


def test_a_download_without_weights_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import huggingface_hub

    def empty(**kwargs: object) -> str:
        Path(str(kwargs["local_dir"])).mkdir(parents=True)
        return str(kwargs["local_dir"])

    monkeypatch.setattr(huggingface_hub, "snapshot_download", empty)

    with pytest.raises(ModelError, match="has no model weights"):
        download_model("acme/not-a-model", tmp_path)

    assert list((tmp_path / "models").iterdir()) == []
