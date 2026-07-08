from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.generation.llm import GroundedGenerator
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import QueryResponse, RetrievedChunk
from legacy_retrieval.retrieval.decompose import build_subqueries
from legacy_retrieval.retrieval.hybrid import HybridRetriever
from legacy_retrieval.retrieval.reranker import CrossEncoderReranker


def _interleave(ranked_lists: list[list[RetrievedChunk]], limit: int) -> list[RetrievedChunk]:
    """Round-robin entre as listas, deduplicando por chunk.

    Garante que cada sub-query contribua com seus melhores resultados —
    sem isso, a entidade com corpus maior domina o top-k.
    """
    merged: list[RetrievedChunk] = []
    seen: set[str] = set()
    for rank in range(max((len(lst) for lst in ranked_lists), default=0)):
        for lst in ranked_lists:
            if rank < len(lst) and lst[rank].chunk.id not in seen:
                seen.add(lst[rank].chunk.id)
                merged.append(lst[rank])
                if len(merged) >= limit:
                    return merged
    return merged


class RetrievalPipeline:
    """End-to-end retrieval + generation pipeline."""

    def __init__(
        self,
        indexer: DocumentIndexer | None = None,
        settings: Settings | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.indexer = indexer or DocumentIndexer(self.settings)
        self.retriever = HybridRetriever(self.indexer, self.settings)
        self.reranker = CrossEncoderReranker(self.settings)
        self.generator = GroundedGenerator(self.settings)

    def _retrieve_reranked(self, question: str, top_n: int) -> list[RetrievedChunk]:
        """Sistema completo: decomposição (se multi-entidade) + híbrido + rerank."""
        pool = self.settings.retrieval_top_k
        subqueries = build_subqueries(question)

        if len(subqueries) == 1:
            candidates = self.retriever.retrieve(question, top_k=pool)
            return self.reranker.rerank(question, candidates, top_n=top_n)

        per_subquery = []
        for subquery in subqueries:
            candidates = self.retriever.retrieve(subquery, top_k=pool)
            per_subquery.append(self.reranker.rerank(subquery, candidates, top_n=top_n))
        return _interleave(per_subquery, top_n)

    def query(self, question: str, top_k: int | None = None) -> QueryResponse:
        reranked = self._retrieve_reranked(question, top_k or self.settings.rerank_top_k)
        return self.generator.generate(question, reranked)

    def retrieve_only(self, question: str, top_k: int | None = None) -> list[str]:
        """Top-k DOCUMENTOS do sistema completo — o ranking que o gerador consome."""
        k = top_k or self.settings.rerank_top_k
        reranked = self._retrieve_reranked(question, self.settings.retrieval_top_k)

        seen: set[str] = set()
        doc_ids: list[str] = []
        for r in reranked:
            if r.chunk.document_id not in seen:
                seen.add(r.chunk.document_id)
                doc_ids.append(r.chunk.document_id)
            if len(doc_ids) >= k:
                break
        return doc_ids
