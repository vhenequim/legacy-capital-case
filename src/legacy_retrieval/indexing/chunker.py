import hashlib
import re

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.models import Chunk, Document


class Chunker:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def chunk_document(self, document: Document) -> list[Chunk]:
        text = document.content
        size = self.settings.chunk_size
        overlap = self.settings.chunk_overlap

        paragraphs = re.split(r"\n\s*\n", text)
        chunks: list[Chunk] = []
        buffer = ""
        chunk_index = 0
        current_page: int | None = None

        for para in paragraphs:
            page_match = re.match(r"\[Page (\d+)\]", para.strip())
            if page_match:
                current_page = int(page_match.group(1))
                para = re.sub(r"\[Page \d+\]\s*", "", para)

            if not para.strip():
                continue

            candidate = f"{buffer}\n\n{para}".strip() if buffer else para
            if len(candidate) <= size:
                buffer = candidate
                continue

            if buffer:
                chunks.append(self._make_chunk(document, buffer, chunk_index, current_page))
                chunk_index += 1

            if len(para) <= size:
                buffer = para
            else:
                words = para.split()
                window: list[str] = []
                word_len = 0
                for word in words:
                    if word_len + len(word) + 1 > size and window:
                        chunk_text = " ".join(window)
                        chunks.append(self._make_chunk(document, chunk_text, chunk_index, current_page))
                        chunk_index += 1
                        overlap_words = window[-max(1, overlap // 5) :]
                        window = overlap_words + [word]
                        word_len = sum(len(w) for w in window) + len(window)
                    else:
                        window.append(word)
                        word_len += len(word) + 1
                buffer = " ".join(window)

        if buffer.strip():
            chunks.append(self._make_chunk(document, buffer, chunk_index, current_page))

        return chunks

    def _make_chunk(
        self,
        document: Document,
        text: str,
        chunk_index: int,
        page: int | None,
    ) -> Chunk:
        chunk_id = self._chunk_id(document.id, chunk_index, text)
        return Chunk(
            id=chunk_id,
            document_id=document.id,
            text=text.strip(),
            chunk_index=chunk_index,
            page=page,
            company=document.company,
            doc_type=str(document.doc_type.value if hasattr(document.doc_type, "value") else document.doc_type),
            published_at=document.published_at,
            metadata={
                "title": document.title,
                "url": document.url,
                "source": document.source,
            },
        )

    @staticmethod
    def _chunk_id(document_id: str, chunk_index: int, text: str) -> str:
        digest = hashlib.sha256(f"{document_id}:{chunk_index}:{text[:200]}".encode()).hexdigest()[
            :12
        ]
        return f"{document_id}_c{chunk_index}_{digest}"
