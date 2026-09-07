"""Shared page chrome for the Streamlit app."""

from __future__ import annotations

import streamlit as st

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Fraunces:opsz,wght@9..144,560;9..144,700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');

html, body, [class*="css"]  {
  font-family: "IBM Plex Sans", sans-serif;
}
h1, h2, h3, .serif {
  font-family: "Fraunces", Georgia, serif !important;
  letter-spacing: -0.02em;
}
.block-container { padding-top: 1.4rem; max-width: 1200px; }
div[data-testid="stMetric"] {
  background: #141a2e;
  border: 1px solid rgba(212,165,116,0.18);
  border-radius: 16px;
  padding: 12px 16px;
}
.hero {
  background: linear-gradient(135deg, #141a2e 0%, #1b2744 52%, #24324f 100%);
  border: 1px solid rgba(212,165,116,0.22);
  border-radius: 22px;
  padding: 28px 32px;
  margin-bottom: 1.2rem;
}
.hero h1 { font-size: 2.3rem; margin-bottom: 0.2rem; }
.muted { color: #9aa3b8; }
.gold { color: #d4a574; }
.card {
  background: #141a2e;
  border: 1px solid rgba(255,255,255,0.06);
  border-radius: 16px;
  padding: 16px 18px;
  margin-bottom: 10px;
}
.tag {
  display: inline-block;
  background: rgba(212,165,116,0.12);
  color: #d4a574;
  border-radius: 999px;
  padding: 2px 10px;
  font-size: 0.75rem;
  margin-right: 6px;
}
hr { border-color: rgba(255,255,255,0.08); }
</style>
"""


def page_setup(title: str, icon: str = "🎓") -> None:
    st.set_page_config(
        page_title=f"{title} · MLE Professor",
        page_icon=icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )
    st.markdown(CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("### MLE Professor")
        st.caption("Personal ML knowledge base & interview coach")
