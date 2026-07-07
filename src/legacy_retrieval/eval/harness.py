import json
from dataclasses import dataclass, field
from pathlib import Path

from legacy_retrieval.eval.metrics import mrr, precision_at_k, recall_at_k, refusal_correct
from legacy_retrieval.models import EvalQuestion
from legacy_retrieval.pipeline import RetrievalPipeline


@dataclass
class EvalResult:
    question_id: str
    category: str
    recall_at_k: float
    precision_at_k: float
    mrr: float
    refusal_correct: bool
    retrieved_doc_ids: list[str] = field(default_factory=list)
    expected_doc_ids: list[str] = field(default_factory=list)
    refused: bool = False


@dataclass
class EvalReport:
    k: int
    results: list[EvalResult] = field(default_factory=list)

    @property
    def mean_recall(self) -> float:
        if not self.results:
            return 0.0
        answerable = [r for r in self.results if r.expected_doc_ids]
        if not answerable:
            return 0.0
        return sum(r.recall_at_k for r in answerable) / len(answerable)

    @property
    def mean_precision(self) -> float:
        if not self.results:
            return 0.0
        answerable = [r for r in self.results if r.expected_doc_ids]
        if not answerable:
            return 0.0
        return sum(r.precision_at_k for r in answerable) / len(answerable)

    @property
    def mean_mrr(self) -> float:
        if not self.results:
            return 0.0
        answerable = [r for r in self.results if r.expected_doc_ids]
        if not answerable:
            return 0.0
        return sum(r.mrr for r in answerable) / len(answerable)

    @property
    def answer_rate(self) -> float:
        answerable = [r for r in self.results if r.expected_doc_ids]
        if not answerable:
            return 0.0
        return sum(1 for r in answerable if r.refusal_correct) / len(answerable)

    @property
    def refusal_rate(self) -> float:
        unanswerable = [r for r in self.results if not r.expected_doc_ids]
        if not unanswerable:
            return 1.0
        return sum(1 for r in unanswerable if r.refusal_correct) / len(unanswerable)

    def to_dict(self) -> dict:
        return {
            "k": self.k,
            "mean_recall_at_k": round(self.mean_recall, 4),
            "mean_precision_at_k": round(self.mean_precision, 4),
            "mean_mrr": round(self.mean_mrr, 4),
            "answer_rate": round(self.answer_rate, 4),
            "refusal_rate": round(self.refusal_rate, 4),
            "per_question": [
                {
                    "id": r.question_id,
                    "category": r.category,
                    "recall_at_k": round(r.recall_at_k, 4),
                    "precision_at_k": round(r.precision_at_k, 4),
                    "mrr": round(r.mrr, 4),
                    "refusal_correct": r.refusal_correct,
                }
                for r in self.results
            ],
        }


def load_questions(path: Path) -> list[EvalQuestion]:
    questions: list[EvalQuestion] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        questions.append(EvalQuestion.model_validate(json.loads(line)))
    return questions


class EvalHarness:
    def __init__(self, pipeline: RetrievalPipeline) -> None:
        self.pipeline = pipeline

    def run(self, questions: list[EvalQuestion], k: int = 10) -> EvalReport:
        report = EvalReport(k=k)

        for q in questions:
            response = self.pipeline.query(q.question, top_k=k)
            retrieved_doc_ids = self.pipeline.retrieve_only(q.question, top_k=k)

            if q.answerable and q.expected_doc_ids:
                result = EvalResult(
                    question_id=q.id,
                    category=q.category,
                    recall_at_k=recall_at_k(retrieved_doc_ids, q.expected_doc_ids, k),
                    precision_at_k=precision_at_k(retrieved_doc_ids, q.expected_doc_ids, k),
                    mrr=mrr(retrieved_doc_ids, q.expected_doc_ids),
                    refusal_correct=refusal_correct(response.refused, q.answerable),
                    retrieved_doc_ids=retrieved_doc_ids,
                    expected_doc_ids=q.expected_doc_ids,
                    refused=response.refused,
                )
            else:
                result = EvalResult(
                    question_id=q.id,
                    category=q.category,
                    recall_at_k=0.0,
                    precision_at_k=0.0,
                    mrr=0.0,
                    refusal_correct=refusal_correct(response.refused, q.answerable),
                    retrieved_doc_ids=retrieved_doc_ids,
                    expected_doc_ids=[],
                    refused=response.refused,
                )

            report.results.append(result)

        return report
