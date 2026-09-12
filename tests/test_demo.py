"""Tests for demo mode. Run: MLE_DATA_DIR=/tmp/... pytest tests/test_demo.py -q"""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, ".")

import demo
from database import get_db


@pytest.fixture()
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("MLE_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("MLE_DEMO_MODE", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    return get_db()


def test_demo_disabled_by_default(monkeypatch):
    monkeypatch.delenv("MLE_DEMO_MODE", raising=False)
    assert demo.demo_enabled() is False


def test_demo_enabled_flag(monkeypatch):
    monkeypatch.setenv("MLE_DEMO_MODE", "1")
    assert demo.demo_enabled() is True
    monkeypatch.setenv("MLE_DEMO_MODE", "false")
    assert demo.demo_enabled() is False


def test_effective_key_falls_back_to_env(monkeypatch):
    # No streamlit installed here -> session state unavailable -> env fallback.
    monkeypatch.setenv("GROQ_API_KEY", "gsk_test")
    assert demo.effective_groq_key() == "gsk_test"


def test_effective_key_empty_without_env(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert demo.effective_groq_key() == ""


def test_seed_is_idempotent(store):
    first = demo.seed_demo_data(store)
    assert first == len(demo.DEMO_PAPERS) > 0
    assert demo.seed_demo_data(store) == 0  # library no longer empty
    assert len(store.list_papers()) == len(demo.DEMO_PAPERS)


def test_seed_does_not_clobber_existing(store):
    store.upsert_paper(id="9999.99999", title="Mine", summary_raw="x")
    assert demo.seed_demo_data(store) == 0
    assert len(store.list_papers()) == 1
