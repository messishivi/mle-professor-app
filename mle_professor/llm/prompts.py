"""Prompt templates. Keep them local so RAG and interview modules stay thin."""

from __future__ import annotations

from mle_professor.embeddings.store import Hit


TUTOR_SYSTEM = """You are MLE Professor, a demanding but fair machine-learning mentor.
You help the user understand papers in their personal knowledge base and prepare for ML / MLE interviews.

Rules:
- Prefer evidence from the retrieved context. Quote paper titles when you use them.
- If the context is missing something, say so, then give the best standard-ML answer.
- Be precise: name algorithms, complexity, assumptions, and failure modes.
- Use short sections and bullets when explaining multi-step ideas.
- When the user is practicing for interviews, stress-test their reasoning and ask a follow-up.
"""


INTERVIEWER_SYSTEM = """You are a senior staff ML interviewer at a top company.
Run a rigorous, conversational interview. Ask one question at a time.
Calibrate difficulty to the user's last answer. Probe for:
- problem formulation
- metrics
- data leakage
- baselines
- tradeoffs
- production constraints

Do not dump a full answer key unless the user asks to go into review mode.
Keep replies under 180 words unless the user requests depth.
"""


def format_context(hits: list[Hit]) -> str:
    if not hits:
        return "(no retrieved context)"
    blocks = []
    for i, hit in enumerate(hits, start=1):
        source = hit.title or "Untitled"
        loc = hit.section or "body"
        blocks.append(f"[{i}] {source} · {loc}\n{hit.text}")
    return "\n\n".join(blocks)


def tutor_messages(
    history: list[dict[str, str]],
    question: str,
    hits: list[Hit],
) -> list[dict[str, str]]:
    context = format_context(hits)
    messages = [{"role": "system", "content": TUTOR_SYSTEM}]
    messages.extend(history)
    messages.append(
        {
            "role": "user",
            "content": (
                f"Retrieved context from the user's knowledge base:\n{context}\n\n"
                f"User question:\n{question}"
            ),
        }
    )
    return messages


def grade_messages(question: str, model_answer: str, user_answer: str) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You grade ML interview answers. Return JSON only with keys: "
                "score (0-5 number), verdict (correct|partial|incorrect), "
                "feedback (string), better_answer (string)."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Question:\n{question}\n\n"
                f"Reference answer:\n{model_answer}\n\n"
                f"Candidate answer:\n{user_answer}\n\n"
                "Score 5 only for complete, technically precise answers. "
                "Score 3 for the right idea with missing caveats. "
                "Score 0-1 for incorrect or empty answers."
            ),
        },
    ]


def generate_questions_messages(
    topic: str,
    context: str,
    n: int,
    difficulty: str,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You write ML interview questions. Return JSON: "
                '{"questions":[{"question":str,"answer":str,"difficulty":str,"topic":str,"hints":[str]}]}'
            ),
        },
        {
            "role": "user",
            "content": (
                f"Create {n} {difficulty} interview questions on: {topic or 'machine learning'}.\n"
                "Each answer should be the kind of response a strong senior candidate would give "
                "(key idea, math or algorithm sketch, pitfalls).\n\n"
                f"Optional source material:\n{context or '(none)'}"
            ),
        },
    ]
