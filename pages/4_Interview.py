from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st

from mle_professor.interview.bank import TOPICS
from mle_professor.llm.prompts import INTERVIEWER_SYSTEM, format_context
from mle_professor.ui.runtime import get_context, llm_banner
from mle_professor.ui.theme import page_setup

page_setup("Interview", "🎯")
ctx = get_context()
llm_banner(ctx)

st.title("Interview prep")
st.caption("Offline question bank, optional Grok grading, paper-grounded mocks.")

tab_quiz, tab_cards, tab_mock, tab_history = st.tabs(
    ["Quiz", "Flashcards", "Mock interview", "History"]
)

DIFFS = ["All", "easy", "medium", "hard"]
TOPIC_OPTS = ["All", *TOPICS]


def _ensure_quiz() -> None:
    if "quiz_index" not in st.session_state:
        st.session_state.quiz_index = 0
    if "quiz_session" not in st.session_state:
        st.session_state.quiz_session = None


with tab_quiz:
    _ensure_quiz()
    col_a, col_b, col_c = st.columns(3)
    topic = col_a.selectbox("Topic", TOPIC_OPTS, key="quiz_topic")
    difficulty = col_b.selectbox("Difficulty", DIFFS, key="quiz_diff")
    n = col_c.slider("Questions", 3, 12, 5, key="quiz_n")
    source = st.radio("Source", ["Question bank", "Generate from library (Grok)"], horizontal=True)

    if st.button("Start quiz", type="primary"):
        try:
            if source.startswith("Question"):
                sid = ctx.interview.start_bank_session(
                    mode="quiz", topic=topic, difficulty=difficulty, n=n
                )
            else:
                if not ctx.llm.configured:
                    st.error("Generating questions needs XAI_API_KEY.")
                    st.stop()
                hits = ctx.retriever.search(topic if topic != "All" else "machine learning", k=6)
                sid = ctx.interview.start_generated_session(
                    topic=topic,
                    n=n,
                    difficulty="medium" if difficulty == "All" else difficulty,
                    context_hits=hits,
                )
            st.session_state.quiz_session = sid
            st.session_state.quiz_index = 0
            st.rerun()
        except Exception as exc:
            st.error(str(exc))

    sid = st.session_state.quiz_session
    if sid:
        items = ctx.store.list_items(sid)
        if not items:
            st.warning("Session has no questions.")
        else:
            idx = min(st.session_state.quiz_index, len(items) - 1)
            item = items[idx]
            st.progress((idx) / len(items))
            st.markdown(f"**Question {idx + 1} / {len(items)}** · {item.topic} · {item.difficulty}")
            st.write(item.question)
            answer = st.text_area("Your answer", key=f"ans-{item.id}", height=160)
            c1, c2, c3 = st.columns(3)
            if c1.button("Submit", type="primary"):
                grade = ctx.interview.submit(item, answer)
                st.session_state[f"grade-{item.id}"] = grade
            grade = st.session_state.get(f"grade-{item.id}")
            if grade:
                st.info(f"{grade.verdict} · {grade.score:.1f}/5\n\n{grade.feedback}")
                with st.expander("Reference answer"):
                    st.write(grade.better_answer or item.model_answer)
            if c2.button("Skip / next", disabled=idx >= len(items) - 1):
                st.session_state.quiz_index = idx + 1
                st.rerun()
            if c3.button("Finish session"):
                session = ctx.interview.finish(sid)
                st.success(
                    f"Score {session.score:.1f} / {session.max_score:.0f}"
                    if session.max_score
                    else "Session closed."
                )
                st.session_state.quiz_session = None

with tab_cards:
    topic = st.selectbox("Topic", TOPIC_OPTS, key="card_topic")
    difficulty = st.selectbox("Difficulty", DIFFS, key="card_diff")
    deck = ctx.interview.flashcard_deck(topic, difficulty)
    if not deck:
        st.info("No cards in that slice.")
    else:
        if "card_i" not in st.session_state:
            st.session_state.card_i = 0
        i = st.session_state.card_i % len(deck)
        card = deck[i]
        st.caption(f"{i + 1} / {len(deck)} · {card.topic} · {card.difficulty}")
        st.markdown(f"### {card.question}")
        if card.hints:
            st.caption("Hints: " + " · ".join(card.hints))
        with st.expander("Reveal answer"):
            st.write(card.answer)
        b1, b2 = st.columns(2)
        if b1.button("Previous"):
            st.session_state.card_i = (i - 1) % len(deck)
            st.rerun()
        if b2.button("Next"):
            st.session_state.card_i = (i + 1) % len(deck)
            st.rerun()

with tab_mock:
    st.write("A live interviewer that can pull from your papers.")
    if "mock_history" not in st.session_state:
        st.session_state.mock_history = [
            {
                "role": "assistant",
                "content": "Let's start. Tell me about a production ML system you would be comfortable defending in depth.",
            }
        ]
    papers = ctx.store.list_papers()
    focus = st.selectbox(
        "Ground in a paper (optional)",
        ["None"] + [f"{p.id} · {p.title}" for p in papers],
        key="mock_focus",
    )
    for msg in st.session_state.mock_history:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])
    user_msg = st.chat_input("Answer the interviewer…", key="mock_in")
    if user_msg:
        st.session_state.mock_history.append({"role": "user", "content": user_msg})
        with st.chat_message("user"):
            st.markdown(user_msg)
        with st.chat_message("assistant"):
            if not ctx.llm.configured:
                text = (
                    "Mock interviews need `XAI_API_KEY`. Use Quiz or Flashcards offline, "
                    "or add a key in Settings."
                )
                st.markdown(text)
                st.session_state.mock_history.append({"role": "assistant", "content": text})
            else:
                paper_id = None if focus == "None" else int(focus.split(" · ", 1)[0])
                hits = ctx.retriever.context_hits(user_msg, paper_id=paper_id)
                messages = [{"role": "system", "content": INTERVIEWER_SYSTEM}]
                if hits:
                    messages.append(
                        {
                            "role": "system",
                            "content": "Optional paper context:\n" + format_context(hits),
                        }
                    )
                messages.extend(st.session_state.mock_history)
                placeholder = st.empty()
                collected = []
                try:
                    for piece in ctx.llm.stream(messages, temperature=0.6):
                        collected.append(piece)
                        placeholder.markdown("".join(collected))
                except Exception as exc:
                    collected = [str(exc)]
                    placeholder.error(str(exc))
                answer = "".join(collected)
                st.session_state.mock_history.append(
                    {"role": "assistant", "content": answer}
                )

with tab_history:
    sessions = ctx.store.list_sessions()
    if not sessions:
        st.info("No sessions yet.")
    for session in sessions:
        label = (
            f"#{session.id} · {session.mode} · {session.topic or 'general'} · "
            f"{session.started_at[:16]}"
        )
        if session.score is not None:
            label += f" · {session.score:.1f}/{session.max_score:.0f}"
        with st.expander(label):
            for item in ctx.store.list_items(session.id):
                st.markdown(f"**{item.question}**")
                if item.user_answer:
                    st.caption("You: " + item.user_answer[:400])
                if item.evaluation:
                    st.caption(item.evaluation)
                st.divider()
