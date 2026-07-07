from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.generation.llm import GroundedGenerator
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import QueryResponse
from legacy_retrieval.retrieval.hybrid import HybridRetriever
from legacy_retrieval.retrieval.reranker import CrossEncoderReranker


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

    def query(self, question: str, top_k: int | None = None) -> QueryResponse:
        retrieved = self.retriever.retrieve(question, top_k=top_k)
        reranked = self.reranker.rerank(question, retrieved)
        return self.generator.generate(question, reranked)

    def retrieve_only(self, question: str, top_k: int | None = None) -> list[str]:
        """Top-k DOCUMENTOS do sistema completo (híbrido + rerank).

        Busca um pool largo de chunks, aplica o reranker e deduplica por
        documento — é o ranking que o gerador realmente consome.
        """
        k = top_k or self.settings.rerank_top_k
        candidates = self.retriever.retrieve(question, top_k=self.settings.retrieval_top_k)
        reranked = self.reranker.rerank(question, candidates, top_n=self.settings.retrieval_top_k)

        seen: set[str] = set()
        doc_ids: list[str] = []
        for r in reranked:
            if r.chunk.document_id not in seen:
                seen.add(r.chunk.document_id)
                doc_ids.append(r.chunk.document_id)
            if len(doc_ids) >= k:
                break
        return doc_ids
