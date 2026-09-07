from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("EMBEDDING_BACKEND", "hash")
os.environ.setdefault("XAI_API_KEY", "")


@pytest.fixture
def data_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MLE_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("EMBEDDING_BACKEND", "hash")
    from mle_professor.config import reset_settings

    reset_settings()
    return tmp_path


@pytest.fixture
def settings(data_dir: Path):
    from mle_professor.config import get_settings

    cfg = get_settings()
    cfg.ensure_dirs()
    return cfg
