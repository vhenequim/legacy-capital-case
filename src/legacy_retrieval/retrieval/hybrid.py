from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import Chunk, RetrievedChunk


def reciprocal_rank_fusion(
    rankings: list[list[tuple[Chunk, float]]],
    k: int = 60,
) -> list[tuple[Chunk, float]]:
    """Fuse multiple ranked lists using RRF."""
    scores: dict[str, float] = {}
    chunks: dict[str, Chunk] = {}

    for ranking in rankings:
        for rank, (chunk, _) in enumerate(ranking, start=1):
            scores[chunk.id] = scores.get(chunk.id, 0.0) + 1.0 / (k + rank)
            chunks[chunk.id] = chunk

    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(chunks[cid], score) for cid, score in fused]


class HybridRetriever:
    def __init__(
        self,
        indexer: DocumentIndexer,
        settings: Settings | None = None,
    ) -> None:
        self.indexer = indexer
        self.settings = settings or get_settings()

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievedChunk]:
        k = top_k or self.settings.retrieval_top_k

        bm25_results = self.indexer.bm25_search(query, top_k=k)
        vector_results = self.indexer.vector_search(query, top_k=k)

        fused = reciprocal_rank_fusion([bm25_results, vector_results])

        return [
            RetrievedChunk(chunk=chunk, score=score, source="hybrid")
            for chunk, score in fused[:k]
        ]

    def retrieve_document_ids(self, query: str, top_k: int | None = None) -> list[str]:
        results = self.retrieve(query, top_k)
        seen: set[str] = set()
        doc_ids: list[str] = []
        for r in results:
            if r.chunk.document_id not in seen:
                seen.add(r.chunk.document_id)
                doc_ids.append(r.chunk.document_id)
        return doc_ids
