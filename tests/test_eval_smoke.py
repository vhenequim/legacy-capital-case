"""Smoke eval de retrieval — gate de regressão para o CI.

Indexa o corpus fixture versionado (eval/fixtures/, 12 documentos reais
truncados) e roda o eval harness completo (híbrido + decomposição + rerank)
com geração local. Só as métricas de retrieval são afirmadas: são
determinísticas e não dependem de API externa.

A recusa semântica não é afirmada aqui — em um corpus minúsculo o gate por
score deixa passar entidade errada com vocabulário certo, e a segunda camada
(LLM grounded) não roda no CI. Ela é coberta pelo eval completo.
"""

import json
from pathlib import Path

import pytest

from legacy_retrieval.config import Settings
from legacy_retrieval.eval.harness import EvalHarness, load_questions
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import Document
from legacy_retrieval.pipeline import RetrievalPipeline

FIXTURES = Path(__file__).resolve().parents[1] / "eval" / "fixtures"

RECALL_FLOOR = 0.9
MRR_FLOOR = 0.7


@pytest.fixture(scope="module")
def smoke_pipeline():
    settings = Settings(
        llm_provider="local",
        embedding_provider="local",
        qdrant_collection="test_smoke_eval",
    )
    docs = [
        Document.model_validate(json.loads(p.read_text(encoding="utf-8")))
        for p in sorted((FIXTURES / "documents").glob("*.json"))
    ]
    assert len(docs) >= 10, "corpus fixture incompleto — rode scripts/build_eval_fixtures.py"

    indexer = DocumentIndexer(settings)
    try:
        indexer.index_documents(docs)
    except ConnectionError:
        pytest.skip("Qdrant indisponível — suba com: docker compose up -d qdrant")

    yield RetrievalPipeline(indexer, settings)

    indexer._get_qdrant().delete_collection("test_smoke_eval")


def test_smoke_retrieval_metrics(smoke_pipeline):
    questions = load_questions(FIXTURES / "questions_smoke.jsonl")
    report = EvalHarness(smoke_pipeline).run(questions, k=5, retrieval_only=True)

    per_q = {
        r.question_id: (r.recall_at_k, r.mrr) for r in report.results if r.expected_doc_ids
    }
    detail = ", ".join(f"{qid}={rec:.2f}" for qid, (rec, _) in sorted(per_q.items()))

    assert report.mean_recall >= RECALL_FLOOR, (
        f"Recall@5 caiu para {report.mean_recall:.2f} (piso {RECALL_FLOOR}) — "
        f"regressão de retrieval. Por pergunta: {detail}"
    )
    assert report.mean_mrr >= MRR_FLOOR, (
        f"MRR caiu para {report.mean_mrr:.2f} (piso {MRR_FLOOR}). Por pergunta: {detail}"
    )


def test_smoke_multi_entity_coverage(smoke_pipeline):
    """A pergunta multi-entidade (s02) deve cobrir AMZN e META no top-5 —
    protege a query decomposition contra regressão."""
    doc_ids = smoke_pipeline.retrieve_only(
        "How much did Amazon and Meta each report in capital expenditures for the full year 2025?",
        top_k=5,
    )
    assert "sec_0001018724_000101872426000002" in doc_ids, f"AMZN fora do top-5: {doc_ids}"
    assert "sec_0001326801_000162828026003832" in doc_ids, f"META fora do top-5: {doc_ids}"
