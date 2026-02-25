"""
quiz_session.py
───────────────
Tracks active quiz sessions per document so the backend remembers
which question the user is on and can reveal answers on demand.
Place this file in your backend/ folder alongside app.py.
"""

from datetime import datetime


class QuizSession:
    """Holds the state for one active quiz on one document."""

    def __init__(self, doc_id: str, questions: list):
        self.doc_id = doc_id
        self.questions = questions
        self.current_index = 0
        self.answers_revealed = set()
        self.user_answers = {}
        self.score = 0
        self.started_at = datetime.now().isoformat()
        self.finished = False

    # ── Navigation ─────────────────────────────────────────────────────────

    def current_question(self):
        if 0 <= self.current_index < len(self.questions):
            return self.questions[self.current_index]
        return None

    def next_question(self):
        if self.current_index < len(self.questions) - 1:
            self.current_index += 1
            return self.current_question()
        self.finished = True
        return None

    def prev_question(self):
        if self.current_index > 0:
            self.current_index -= 1
            return self.current_question()
        return None

    # ── Answer handling ────────────────────────────────────────────────────

    def reveal_answer(self):
        """Mark current question as revealed and return full answer info."""
        q = self.current_question()
        if not q:
            return {"error": "No active question"}

        self.answers_revealed.add(self.current_index)
        qtype = q.get("type", "")

        response = {
            "question_id":   self.current_index,
            "question_text": q.get("question", ""),
            "type":          qtype,
            "answer":        q.get("answer", ""),
            "explanation":   q.get("explanation", ""),
            "context":       q.get("context", ""),
        }

        if qtype == "multiple_choice":
            response["revealed_message"] = (
                f'The correct answer is: "{q["answer"]}". '
                f'{q.get("explanation", "")}'
            )
        elif qtype == "fill_blank":
            response["revealed_message"] = (
                f'The missing word is: "{q["answer"]}". '
                f'{q.get("explanation", "")}'
            )
        elif qtype == "short_answer":
            response["revealed_message"] = (
                f'The answer is: "{q["answer"]}". '
                f'{q.get("explanation", "")}'
            )
        elif qtype == "true_false":
            response["revealed_message"] = (
                f'The answer is: {q["answer"]}. '
                f'{q.get("explanation", "")}'
            )
        else:
            response["revealed_message"] = f'Answer: {q.get("answer", "N/A")}'

        return response

    def submit_answer(self, user_answer: str):
        """Check the user's answer against the correct one."""
        q = self.current_question()
        if not q:
            return {"error": "No active question"}

        correct = q.get("answer", "").strip().lower()
        given   = user_answer.strip().lower()

        is_correct = (
            given == correct
            or correct in given
            or given in correct
        )

        if is_correct:
            self.score += 1

        self.user_answers[self.current_index] = user_answer
        self.answers_revealed.add(self.current_index)

        return {
            "is_correct":      is_correct,
            "correct_answer":  q.get("answer", ""),
            "user_answer":     user_answer,
            "explanation":     q.get("explanation", ""),
            "score":           self.score,
            "question_number": self.current_index + 1,
            "total_questions": len(self.questions),
            "message": (
                f'{"Correct!" if is_correct else "Not quite."} '
                f'The answer is "{q["answer"]}". '
                f'{q.get("explanation", "")}'
            )
        }

    # ── Summary ────────────────────────────────────────────────────────────

    def get_summary(self):
        total = len(self.questions)
        pct   = round((self.score / total) * 100) if total else 0
        return {
            "score":            self.score,
            "total":            total,
            "percentage":       pct,
            "answers_revealed": len(self.answers_revealed),
            "finished":         self.finished,
            "message": (
                f"Quiz complete! You scored {self.score}/{total} ({pct}%)"
            )
        }

    def to_dict(self):
        return {
            "doc_id":           self.doc_id,
            "questions":        self.questions,
            "current_index":    self.current_index,
            "current_question": self.current_question(),
            "total_questions":  len(self.questions),
            "score":            self.score,
            "finished":         self.finished,
            "answers_revealed": list(self.answers_revealed),
        }


# ─────────────────────────────────────────────────────────────────────────────
#  Session registry  (one session per doc_id, lives in memory)
# ─────────────────────────────────────────────────────────────────────────────

class QuizSessionManager:

    def __init__(self):
        self._sessions = {}

    def start(self, doc_id: str, questions: list) -> QuizSession:
        session = QuizSession(doc_id, questions)
        self._sessions[doc_id] = session
        return session

    def get(self, doc_id: str):
        return self._sessions.get(doc_id)

    def end(self, doc_id: str):
        self._sessions.pop(doc_id, None)

    def has_active(self, doc_id: str) -> bool:
        s = self._sessions.get(doc_id)
        return s is not None and not s.finished