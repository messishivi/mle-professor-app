"""Quiz, flashcards, and generated interviews on top of the bank + LLM."""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Optional

from mle_professor.db.sqlite import InterviewItem, InterviewSession, PaperStore
from mle_professor.embeddings.store import Hit
from mle_professor.interview.bank import BankQuestion, questions_for
from mle_professor.llm.client import LLMClient, LLMNotConfigured
from mle_professor.llm.prompts import generate_questions_messages, grade_messages


@dataclass
class Grade:
    score: float
    verdict: str
    feedback: str
    better_answer: str


class InterviewEngine:
    def __init__(self, store: PaperStore, llm: LLMClient) -> None:
        self.store = store
        self.llm = llm

    def start_bank_session(
        self,
        *,
        mode: str,
        topic: str = "All",
        difficulty: str = "All",
        n: int = 5,
        paper_id: Optional[int] = None,
    ) -> int:
        pool = questions_for(None if topic == "All" else topic, difficulty=difficulty)
        if not pool:
            raise ValueError("No questions in that slice of the bank.")
        pick = pool[:]
        random.shuffle(pick)
        pick = pick[: max(1, n)]
        session_id = self.store.start_session(mode=mode, topic=topic, paper_id=paper_id)
        for q in pick:
            self.store.add_item(
                session_id,
                question=q.question,
                model_answer=q.answer,
                question_id=q.id,
                difficulty=q.difficulty,
                topic=q.topic,
            )
        return session_id

    def start_generated_session(
        self,
        *,
        topic: str,
        n: int,
        difficulty: str,
        context_hits: list[Hit],
        paper_id: Optional[int] = None,
    ) -> int:
        context = "\n\n".join(h.text for h in context_hits[:6]) if context_hits else ""
        payload = self.llm.json_chat(
            generate_questions_messages(topic, context, n, difficulty)
        )
        questions = payload.get("questions") if isinstance(payload, dict) else payload
        if not isinstance(questions, list) or not questions:
            raise ValueError("The model did not return any questions.")
        session_id = self.store.start_session(
            mode="generated", topic=topic, paper_id=paper_id
        )
        for raw in questions[:n]:
            if not isinstance(raw, dict):
                continue
            q = str(raw.get("question") or "").strip()
            a = str(raw.get("answer") or "").strip()
            if not q:
                continue
            self.store.add_item(
                session_id,
                question=q,
                model_answer=a,
                difficulty=str(raw.get("difficulty") or difficulty),
                topic=str(raw.get("topic") or topic),
            )
        return session_id

    def grade(
        self, question: str, model_answer: str, user_answer: str
    ) -> Grade:
        text = (user_answer or "").strip()
        if not text:
            return Grade(0.0, "incorrect", "Empty answer.", model_answer)
        if not self.llm.configured:
            return Grade(
                score=0.0,
                verdict="ungraded",
                feedback="Saved. Set XAI_API_KEY to auto-grade against the reference answer.",
                better_answer=model_answer,
            )
        try:
            payload = self.llm.json_chat(
                grade_messages(question, model_answer, text)
            )
        except (LLMNotConfigured, Exception) as exc:
            return Grade(
                0.0,
                "ungraded",
                f"Could not grade: {exc}",
                model_answer,
            )
        score = float(payload.get("score", 0) or 0)
        score = max(0.0, min(5.0, score))
        verdict = str(payload.get("verdict") or "partial")
        feedback = str(payload.get("feedback") or "")
        better = str(payload.get("better_answer") or model_answer)
        return Grade(score, verdict, feedback, better)

    def submit(self, item: InterviewItem, user_answer: str) -> Grade:
        grade = self.grade(item.question, item.model_answer, user_answer)
        self.store.record_answer(
            item.id,
            user_answer=user_answer,
            evaluation=f"{grade.verdict}: {grade.feedback}",
            score=grade.score,
        )
        return grade

    def finish(self, session_id: int) -> InterviewSession:
        return self.store.complete_session(session_id)

    @staticmethod
    def flashcard_deck(
        topic: str = "All", difficulty: str = "All"
    ) -> list[BankQuestion]:
        deck = questions_for(None if topic == "All" else topic, difficulty=difficulty)
        random.shuffle(deck)
        return deck
