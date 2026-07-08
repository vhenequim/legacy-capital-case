from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.generation.llm import GroundedGenerator
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import QueryResponse, RetrievedChunk
from legacy_retrieval.retrieval.decompose import (
    NEUTRAL_COMPANIES,
    build_subqueries,
    corpus_companies,
    detect_companies,
)
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
        """Sistema completo: decomposição (se multi-entidade) + híbrido + rerank + entity boost."""
        pool = self.settings.retrieval_top_k
        subqueries = build_subqueries(question)

        if len(subqueries) == 1:
            return self._retrieve_single(question, pool, top_n)

        per_subquery = [self._retrieve_single(sq, pool, top_n) for sq in subqueries]
        return _interleave(per_subquery, top_n)

    def _retrieve_single(self, query: str, pool: int, top_n: int) -> list[RetrievedChunk]:
        companies = (
            corpus_companies(detect_companies(query)) if self.settings.entity_boost else set()
        )
        candidates = self.retriever.retrieve(query, top_k=pool, companies=companies or None)
        reranked = self.reranker.rerank(query, candidates, top_n=pool)

        if companies:
            # Chunks de OUTRA empresa conhecida caem no ranking; fontes
            # neutras (BACEN) e a própria empresa ficam intactas. O score
            # original é preservado (o gate de recusa lê o logit real).
            penalty = self.settings.entity_mismatch_penalty
            allowed = companies | NEUTRAL_COMPANIES

            def adjusted(r: RetrievedChunk) -> float:
                return r.score - (0.0 if r.chunk.company in allowed else penalty)

            reranked.sort(key=adjusted, reverse=True)

        return reranked[:top_n]

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
