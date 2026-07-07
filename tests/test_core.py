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
    content = "word " * 300
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
            "instituicao": ["NU PAGAMENTOS", "OTHER"],
            "carteira_ativa": [100, 900],
            "carteira_total_sistema": [1000, 1000],
            "data_base": ["2024-09", "2024-09"],
        }
    )
    result = calculate_market_share(df, "NU PAGAMENTOS")
    assert result.iloc[0]["market_share"] == pytest.approx(0.1)


def test_pipeline_query_with_demo_docs():
    from legacy_retrieval.indexing.indexer import DocumentIndexer
    from legacy_retrieval.pipeline import RetrievalPipeline

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
    indexer = DocumentIndexer()
    indexer.index_documents(docs)
    pipeline = RetrievalPipeline(indexer)

    response = pipeline.query("What is Microsoft capex guidance for 2025?")
    assert not response.refused
    assert "80" in response.answer or "billion" in response.answer.lower()

    refused = pipeline.query("xyzzy completely unrelated quantum physics zebra topic")
    assert refused.refused
