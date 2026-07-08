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

    def retrieve(
        self,
        query: str,
        top_k: int | None = None,
        companies: set[str] | None = None,
    ) -> list[RetrievedChunk]:
        """Busca híbrida BM25 + vetorial com fusão RRF.

        Quando `companies` é dado, rankings adicionais restritos a essas
        empresas entram na fusão — garante que chunks da entidade da
        pergunta estejam no pool mesmo quando o corpus inteiro compete
        (ex.: RPO enterrado em notas de 10-Q vs press releases alheios).
        """
        k = top_k or self.settings.retrieval_top_k

        rankings = [
            self.indexer.bm25_search(query, top_k=k),
            self.indexer.vector_search(query, top_k=k),
        ]
        if companies:
            rankings.append(self.indexer.bm25_search(query, top_k=k, companies=companies))
            rankings.append(self.indexer.vector_search(query, top_k=k, companies=companies))

        fused = reciprocal_rank_fusion(rankings)

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
