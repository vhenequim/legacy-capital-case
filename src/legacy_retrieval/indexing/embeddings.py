from abc import ABC, abstractmethod

import numpy as np

from legacy_retrieval.config import Settings, get_settings


class EmbeddingProvider(ABC):
    @abstractmethod
    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        ...

    @property
    @abstractmethod
    def dimension(self) -> int:
        ...


class LocalEmbeddingProvider(EmbeddingProvider):
    def __init__(self, model_name: str = "intfloat/multilingual-e5-small") -> None:
        from sentence_transformers import SentenceTransformer

        self._model = SentenceTransformer(model_name)
        self._dimension = self._model.get_embedding_dimension()
        # Modelos E5 exigem prefixos assimétricos query:/passage:
        self._use_e5_prefix = "e5" in model_name.lower()

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        if self._use_e5_prefix:
            prefix = "query: " if is_query else "passage: "
            texts = [prefix + t for t in texts]
        vectors = self._model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        return [v.tolist() for v in vectors]

    @property
    def dimension(self) -> int:
        return int(self._dimension)


class OpenAIEmbeddingProvider(EmbeddingProvider):
    def __init__(self, settings: Settings | None = None) -> None:
        from openai import OpenAI

        self.settings = settings or get_settings()
        self._client = OpenAI(api_key=self.settings.openai_api_key)
        self._dimension = 1536

    def embed(self, texts: list[str], is_query: bool = False) -> list[list[float]]:
        response = self._client.embeddings.create(
            model=self.settings.openai_embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension


def get_embedding_provider(settings: Settings | None = None) -> EmbeddingProvider:
    settings = settings or get_settings()
    if settings.embedding_provider == "openai" and settings.openai_api_key:
        return OpenAIEmbeddingProvider(settings)
    return LocalEmbeddingProvider(settings.embedding_model)


def cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a)
    vb = np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)
