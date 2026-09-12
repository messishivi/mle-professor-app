"""Demo mode: try the app without forking, cloning, or a ``.env`` file.

Enable with ``MLE_DEMO_MODE=1``. The app then:

- seeds a few sample papers the first time the library is empty,
- shows a demo banner,
- accepts a bring-your-own Groq key from a sidebar field that lives in
  ``st.session_state`` only — it is never written to disk or the database.

When the flag is off, everything behaves exactly as before.
"""

from __future__ import annotations

import os
from typing import Optional

_TRUE = {"1", "true", "yes", "on"}


def demo_enabled() -> bool:
    """True when ``MLE_DEMO_MODE`` is set to a truthy value."""
    return os.getenv("MLE_DEMO_MODE", "").strip().lower() in _TRUE


def _session_state() -> Optional[dict]:
    """Return Streamlit session state, or None outside a Streamlit run."""
    try:
        import streamlit as st

        return st.session_state
    except Exception:
        return None


def effective_groq_key() -> str:
    """Session key first (demo BYOK), then the ``GROQ_API_KEY`` environment."""
    state = _session_state()
    if state is not None:
        try:
            key = str(state.get("demo_groq_key") or "").strip()
        except Exception:
            key = ""
        if key:
            return key
    return os.getenv("GROQ_API_KEY", "").strip()


# Short, factual blurbs (not verbatim abstracts) so the demo is useful in 10 seconds.
DEMO_PAPERS = [
    {
        "id": "2106.09685",
        "title": "LoRA: Low-Rank Adaptation of Large Language Models",
        "authors": "Edward J. Hu, Yelong Shen, Phillip Wallis, Zeyuan Allen-Zhu, "
        "Yuanzhi Li, Shean Wang, Lu Wang, Weizhu Chen",
        "published_date": "2021-10-16",
        "summary_raw": (
            "Freezes pretrained weights and injects trainable low-rank matrices "
            "(delta_W = B @ A) into each Transformer layer. Cuts trainable parameters "
            "~10,000x vs full fine-tuning (GPT-3 175B) with on-par quality and, unlike "
            "adapters, no extra inference latency because the update merges into W0."
        ),
    },
    {
        "id": "2205.14135",
        "title": "FlashAttention: Fast and Memory-Efficient Exact Attention with IO-Awareness",
        "authors": "Tri Dao, Daniel Y. Fu, Stefano Ermon, Atri Rudra, Christopher Re",
        "published_date": "2022-05-27",
        "summary_raw": (
            "Exact attention rewritten to be IO-aware: tiling across SRAM/HBM plus "
            "recomputation in the backward pass. 2-4x faster than standard attention, "
            "memory linear in sequence length, no approximation."
        ),
    },
    {
        "id": "2305.18290",
        "title": "Direct Preference Optimization: Your Language Model is Secretly a Reward Model",
        "authors": "Rafael Rafailov, Archit Sharma, Eric Mitchell, Stefano Ermon, "
        "Christopher D. Manning, Chelsea Finn",
        "published_date": "2023-05-29",
        "summary_raw": (
            "Replaces the RLHF pipeline (reward model + PPO) with a closed-form "
            "classification loss derived from the Bradley-Terry preference model. "
            "Fine-tunes directly on preference pairs; simpler and more stable than PPO."
        ),
    },
]


def seed_demo_data(store) -> int:
    """Insert sample papers if the library is empty. Returns the count added."""
    try:
        existing = store.list_papers()
    except Exception:
        return 0
    if existing:
        return 0
    added = 0
    for paper in DEMO_PAPERS:
        try:
            store.upsert_paper(**paper)
            added += 1
        except Exception:
            continue
    return added


def render_demo_banner() -> None:
    """Demo banner + session-only key field. Call once inside the sidebar."""
    import streamlit as st

    st.info(
        "Demo mode — explore freely. Data is ephemeral and nothing is saved. "
        "Add your own Groq key below to unlock the Consultant Terminal."
    )
    st.text_input(
        "Groq API key (this session only)",
        type="password",
        key="demo_groq_key",
        help="Kept in memory for this browser session. Never written to disk.",
    )
