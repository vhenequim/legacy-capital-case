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
        return self.retriever.retrieve_document_ids(question, top_k=top_k)
