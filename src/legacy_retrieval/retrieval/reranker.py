from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.models import RetrievedChunk


class CrossEncoderReranker:
    def __init__(self, settings: Settings | None = None, model_name: str | None = None) -> None:
        self.settings = settings or get_settings()
        self._model = None
        self._model_name = model_name or "cross-encoder/ms-marco-MiniLM-L-6-v2"
        self._available: bool | None = None

    def _load_model(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self._model_name)
            self._available = True
        except Exception:
            self._available = False
        return self._available

    def rerank(self, query: str, results: list[RetrievedChunk]) -> list[RetrievedChunk]:
        if not results:
            return []

        if not self._load_model():
            return sorted(results, key=lambda r: r.score, reverse=True)

        pairs = [(query, r.chunk.text) for r in results]
        scores = self._model.predict(pairs)

        reranked = [
            RetrievedChunk(chunk=r.chunk, score=float(s), source="rerank")
            for r, s in zip(results, scores, strict=True)
        ]
        reranked.sort(key=lambda r: r.score, reverse=True)
        return reranked[: self.settings.rerank_top_k]
