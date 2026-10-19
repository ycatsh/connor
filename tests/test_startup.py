import subprocess
import sys

import pytest

HEAVY = ("numpy", "pypdfium2", "model2vec", "tokenizers", "huggingface_hub")


@pytest.mark.parametrize("module", ["connor.cli.main", "connor.core.names"])
def test_light_commands_never_load_the_heavy_stack(module: str) -> None:
    code = (
        f"import sys, {module}; "
        f"print(','.join(m for m in {HEAVY!r} if m in sys.modules))"
    )

    loaded = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout.strip()

    assert loaded == ""
