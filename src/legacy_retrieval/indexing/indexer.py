import hashlib
import json
import pickle
import re
from pathlib import Path

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams
from rank_bm25 import BM25Okapi

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.indexing.chunker import Chunker
from legacy_retrieval.indexing.embeddings import EmbeddingProvider, get_embedding_provider
from legacy_retrieval.models import Chunk, Document

# Qdrant limits request body to 32 MB — batch upserts and keep payloads small.
UPSERT_BATCH_SIZE = 64
EMBED_BATCH_SIZE = 32
PAYLOAD_TEXT_EXCERPT = 300


class DocumentIndexer:
    def __init__(
        self,
        settings: Settings | None = None,
        embedding_provider: EmbeddingProvider | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedding_provider = embedding_provider or get_embedding_provider(self.settings)
        self.chunker = Chunker(self.settings)
        self._chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None
        self._tokenized_corpus: list[list[str]] = []
        self._qdrant: QdrantClient | None = None

    def _get_qdrant(self) -> QdrantClient:
        if self._qdrant is None:
            client = QdrantClient(url=self.settings.qdrant_url, check_compatibility=False)
            try:
                client.get_collections()
            except Exception as exc:
                raise ConnectionError(
                    f"Qdrant indisponível em {self.settings.qdrant_url}. "
                    "Suba o serviço com: docker compose up -d qdrant"
                ) from exc
            self._qdrant = client
        return self._qdrant

    def _ensure_collection(self) -> None:
        client = self._get_qdrant()
        collections = [c.name for c in client.get_collections().collections]
        if self.settings.qdrant_collection not in collections:
            client.create_collection(
                collection_name=self.settings.qdrant_collection,
                vectors_config=VectorParams(
                    size=self.embedding_provider.dimension,
                    distance=Distance.COSINE,
                ),
            )

    def index_documents(self, documents: list[Document]) -> list[Chunk]:
        all_chunks: list[Chunk] = []
        for doc in documents:
            all_chunks.extend(self.chunker.chunk_document(doc))

        if not all_chunks:
            return []

        self._chunks.extend(all_chunks)
        self._rebuild_bm25()
        self._index_vectors(all_chunks)
        return all_chunks

    _TOKEN_RE = re.compile(r"[a-z0-9áàâãéêíóôõúç]+")

    def _tokenize(self, text: str) -> list[str]:
        return self._TOKEN_RE.findall(text.lower())

    def _rebuild_bm25(self) -> None:
        self._tokenized_corpus = [self._tokenize(c.text) for c in self._chunks]
        self._bm25 = BM25Okapi(self._tokenized_corpus)

    def _index_vectors(self, chunks: list[Chunk]) -> None:
        self._ensure_collection()
        client = self._get_qdrant()

        for batch_start in range(0, len(chunks), EMBED_BATCH_SIZE):
            batch_chunks = chunks[batch_start : batch_start + EMBED_BATCH_SIZE]
            vectors = self.embedding_provider.embed([c.text for c in batch_chunks])
            points = [
                self._make_point(chunk, vector)
                for chunk, vector in zip(batch_chunks, vectors, strict=True)
            ]

            for upsert_start in range(0, len(points), UPSERT_BATCH_SIZE):
                batch_points = points[upsert_start : upsert_start + UPSERT_BATCH_SIZE]
                client.upsert(
                    collection_name=self.settings.qdrant_collection,
                    points=batch_points,
                    wait=True,
                )

    @staticmethod
    def _make_point(chunk: Chunk, vector: list[float]) -> PointStruct:
        # ID determinístico: hash() do Python é salteado por processo e
        # geraria pontos duplicados a cada reindexação.
        point_id = int.from_bytes(
            hashlib.sha256(chunk.id.encode()).digest()[:8], "big", signed=False
        ) % (2**63)
        return PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "company": chunk.company,
                "doc_type": chunk.doc_type,
                "published_at": chunk.published_at.isoformat() if chunk.published_at else None,
                "page": chunk.page,
                # Short excerpt only — full text lives in chunks.json / BM25 index
                "excerpt": chunk.text[:PAYLOAD_TEXT_EXCERPT],
            },
        )

    def bm25_search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        if not self._bm25 or not self._chunks:
            return []

        scores = self._bm25.get_scores(self._tokenize(query))
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
        return [(self._chunks[i], float(s)) for i, s in ranked]

    def vector_search(self, query: str, top_k: int) -> list[tuple[Chunk, float]]:
        if not self._chunks:
            return []

        query_vector = self.embedding_provider.embed([query], is_query=True)[0]
        client = self._get_qdrant()

        results = client.query_points(
            collection_name=self.settings.qdrant_collection,
            query=query_vector,
            limit=top_k,
        ).points

        chunk_by_id = {c.id: c for c in self._chunks}
        output: list[tuple[Chunk, float]] = []
        for hit in results:
            chunk_id = hit.payload.get("chunk_id", "")
            chunk = chunk_by_id.get(chunk_id)
            if chunk is None and hit.payload.get("excerpt"):
                # Fallback if chunks not loaded in memory (should not happen in normal flow)
                continue
            if chunk:
                output.append((chunk, float(hit.score)))
        return output

    def get_chunk_by_id(self, chunk_id: str) -> Chunk | None:
        for c in self._chunks:
            if c.id == chunk_id:
                return c
        return None

    def get_chunks_by_document_id(self, document_id: str) -> list[Chunk]:
        return [c for c in self._chunks if c.document_id == document_id]

    @property
    def chunks(self) -> list[Chunk]:
        return list(self._chunks)

    def save_state(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        chunks_file = path / "chunks.json"
        chunks_file.write_text(
            json.dumps([c.model_dump(mode="json") for c in self._chunks], indent=2),
            encoding="utf-8",
        )
        if self._tokenized_corpus:
            with open(path / "bm25.pkl", "wb") as f:
                pickle.dump(self._tokenized_corpus, f)

    def load_state(self, path: Path) -> None:
        chunks_file = path / "chunks.json"
        if not chunks_file.exists():
            return
        raw = json.loads(chunks_file.read_text(encoding="utf-8"))
        self._chunks = [Chunk.model_validate(c) for c in raw]
        bm25_file = path / "bm25.pkl"
        if bm25_file.exists():
            with open(bm25_file, "rb") as f:
                self._tokenized_corpus = pickle.load(f)
            self._bm25 = BM25Okapi(self._tokenized_corpus)
        else:
            self._rebuild_bm25()
