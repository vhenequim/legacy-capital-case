from datetime import datetime

import pandas as pd
import pytest

from legacy_retrieval.eval.metrics import mrr, precision_at_k, recall_at_k, refusal_correct
from legacy_retrieval.indexing.chunker import Chunker
from legacy_retrieval.models import DocType, Document
from legacy_retrieval.retrieval.hybrid import reciprocal_rank_fusion
from legacy_retrieval.structured.market_share import calculate_market_share
from legacy_retrieval.structured.metrics import extract_metrics


def _make_doc(doc_id: str, company: str, content: str) -> Document:
    return Document(
        id=doc_id,
        source="test",
        company=company,
        doc_type=DocType.FILING,
        published_at=datetime(2024, 1, 1),
        content=content,
    )


def test_recall_at_k():
    retrieved = ["a", "b", "c", "d"]
    expected = ["b", "e"]
    assert recall_at_k(retrieved, expected, k=3) == 0.5


def test_precision_at_k():
    retrieved = ["a", "b", "c"]
    expected = ["b", "c", "d"]
    assert precision_at_k(retrieved, expected, k=3) == pytest.approx(2 / 3)


def test_mrr():
    retrieved = ["x", "y", "target", "z"]
    assert mrr(retrieved, ["target"]) == pytest.approx(1 / 3)


def test_refusal_correct():
    assert refusal_correct(refused=True, answerable=False) is True
    assert refusal_correct(refused=False, answerable=True) is True
    assert refusal_correct(refused=True, answerable=True) is False


def test_chunker_splits_long_document():
    content = "word " * 800  # ~4000 chars > chunk_size (1800)
    doc = _make_doc("doc1", "TEST", content)
    chunker = Chunker()
    chunks = chunker.chunk_document(doc)
    assert len(chunks) > 1
    assert all(c.document_id == "doc1" for c in chunks)


def test_reciprocal_rank_fusion():
    from legacy_retrieval.models import Chunk

    c1 = Chunk(id="c1", document_id="d1", text="a", chunk_index=0)
    c2 = Chunk(id="c2", document_id="d2", text="b", chunk_index=0)
    c3 = Chunk(id="c3", document_id="d3", text="c", chunk_index=0)

    list1 = [(c1, 0.9), (c2, 0.5)]
    list2 = [(c2, 0.8), (c3, 0.6)]
    fused = reciprocal_rank_fusion([list1, list2])
    ids = [c.id for c, _ in fused]
    assert ids[0] == "c2"


def test_extract_rpo_metrics():
    text = "Salesforce reported remaining performance obligations of $48.3 billion as of Q3 FY2024."
    points = extract_metrics(text, "CRM", "rpo")
    assert len(points) >= 1
    assert points[0].value == pytest.approx(48.3e9)


def test_market_share_calculation():
    df = pd.DataFrame(
        {
            "cod_inst": ["18236120", "30680829", "60746948"],
            "instituicao": ["NU PAGAMENTOS", "NU FINANCEIRA", "BRADESCO"],
            "carteira_credito": [60.0, 40.0, 900.0],
            "carteira_total_sistema": [1000.0, 1000.0, 1000.0],
            "data_base": ["202603", "202603", "202603"],
        }
    )
    # Grupo econômico soma as duas entidades do Nubank
    result = calculate_market_share(df, "NUBANK")
    assert result is not None
    assert result["market_share"] == pytest.approx(0.1)

    # Busca por nome de instituição individual
    result = calculate_market_share(df, "BRADESCO")
    assert result["market_share"] == pytest.approx(0.9)


def test_pipeline_query_end_to_end():
    from legacy_retrieval.config import Settings
    from legacy_retrieval.indexing.indexer import DocumentIndexer
    from legacy_retrieval.pipeline import RetrievalPipeline

    # Geração local (sem API externa) e collection isolada para o teste.
    # Threshold relaxado: docs sintéticos de uma frase pontuam mais baixo
    # que conteúdo real no cross-encoder.
    settings = Settings(
        llm_provider="local",
        embedding_provider="local",
        qdrant_collection="test_legacy_pipeline",
        rerank_refusal_threshold=-5.0,
    )

    docs = [
        _make_doc(
            "msft_capex",
            "MSFT",
            "Microsoft expects capital expenditure of approximately $80 billion in FY2025 for AI infrastructure.",
        ),
        _make_doc(
            "nvda_demand",
            "NVDA",
            "NVIDIA noted unprecedented demand for AI infrastructure from hyperscalers.",
        ),
    ]
    indexer = DocumentIndexer(settings)
    try:
        indexer.index_documents(docs)
    except ConnectionError:
        pytest.skip("Qdrant indisponível — suba com: docker compose up -d qdrant")

    try:
        pipeline = RetrievalPipeline(indexer, settings)

        response = pipeline.query("What is Microsoft capex guidance for 2025?")
        assert not response.refused
        assert "80" in response.answer or "billion" in response.answer.lower()

        refused = pipeline.query("xyzzy completely unrelated quantum physics zebra topic")
        assert refused.refused
    finally:
        indexer._get_qdrant().delete_collection("test_legacy_pipeline")


def test_rpo_extraction_press_release_styles():
    from legacy_retrieval.structured.rpo import best_total_rpo, extract_rpo_observations

    # Estilo Salesforce: "Total Remaining Performance Obligation $63B, up 11% Y/Y"
    doc = _make_doc(
        "crm_8k",
        "CRM",
        "Salesforce Announces Results. Total Remaining Performance Obligation $63B, up 11% Y/Y.",
    )
    best = best_total_rpo(extract_rpo_observations(doc))
    assert best is not None
    assert best.value == pytest.approx(63e9)
    assert best.stated_yoy_pct == pytest.approx(11.0)

    # Estilo Palo Alto: "grew 21% year over year to $13.0 billion"
    doc = _make_doc(
        "panw_8k",
        "PANW",
        "Remaining performance obligation grew 21% year over year to $13.0 billion.",
    )
    best = best_total_rpo(extract_rpo_observations(doc))
    assert best.value == pytest.approx(13e9)
    assert best.stated_yoy_pct == pytest.approx(21.0)


def test_rpo_extraction_ignores_guidance_range():
    from legacy_retrieval.structured.rpo import extract_rpo_observations

    doc = _make_doc(
        "panw_guidance",
        "PANW",
        "FY 2026 Guidance: Remaining Performance Obligation $15.2B - $15.3B, 19% - 20% y/y.",
    )
    assert extract_rpo_observations(doc) == []


def test_rpo_extraction_crpo_is_not_total():
    from legacy_retrieval.structured.rpo import best_total_rpo, extract_rpo_observations

    doc = _make_doc(
        "crm_q1",
        "CRM",
        "Current remaining performance obligation of $29.6 billion, up 12% Y/Y.",
    )
    obs = extract_rpo_observations(doc)
    assert len(obs) == 1
    assert obs[0].metric == "crpo"
    assert best_total_rpo(obs) is None


def test_metrics_with_alternative_groups():
    # Grupo satisfeito por qualquer alternativa (8-K OU 10-Q do mesmo dia)
    expected = [["doc_8k", "doc_10q"], "doc_unico"]
    assert recall_at_k(["doc_10q", "x", "doc_unico"], expected, k=3) == 1.0
    assert recall_at_k(["doc_10q", "x", "y"], expected, k=3) == 0.5
    assert mrr(["x", "doc_8k"], expected) == pytest.approx(0.5)


def test_detect_companies_multi_entity():
    from legacy_retrieval.retrieval.decompose import build_subqueries, detect_companies

    q = "How much did Amazon and Meta each report in capital expenditures for 2025?"
    assert detect_companies(q) == ["AMZN", "META"]
    subs = build_subqueries(q)
    assert len(subs) == 2
    assert "Meta" not in subs[0] and "Amazon" in subs[0]
    assert "Amazon" not in subs[1] and "Meta" in subs[1]


def test_detect_companies_ambiguous_alias_pt():
    from legacy_retrieval.retrieval.decompose import build_subqueries, detect_companies

    # "meta" minúsculo é palavra comum em PT — não pode virar a empresa Meta
    q = "Qual a meta de crescimento da carteira que o Bradesco anunciou?"
    assert detect_companies(q) == ["BBD"]
    assert build_subqueries(q) == [q]


def test_single_company_not_decomposed():
    from legacy_retrieval.retrieval.decompose import build_subqueries

    q = "What did NVIDIA say about Blackwell demand?"
    assert build_subqueries(q) == [q]


def test_interleave_round_robin_dedupes():
    from legacy_retrieval.models import Chunk, RetrievedChunk
    from legacy_retrieval.pipeline import _interleave

    def rc(cid, doc):
        return RetrievedChunk(
            chunk=Chunk(id=cid, document_id=doc, text="x", chunk_index=0), score=1.0
        )

    a = [rc("a1", "docA"), rc("shared", "docS"), rc("a3", "docA")]
    b = [rc("b1", "docB"), rc("shared", "docS"), rc("b3", "docB")]
    merged = _interleave([a, b], limit=10)
    ids = [r.chunk.id for r in merged]
    assert ids == ["a1", "b1", "shared", "a3", "b3"]
