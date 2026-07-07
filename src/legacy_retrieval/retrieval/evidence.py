from legacy_retrieval.models import Citation, RetrievedChunk


class EvidenceBuilder:
    def build(self, results: list[RetrievedChunk], max_chars: int = 8000) -> tuple[str, list[Citation]]:
        citations: list[Citation] = []
        parts: list[str] = []
        total = 0

        for i, result in enumerate(results, start=1):
            chunk = result.chunk
            excerpt = chunk.text[:500]
            citation = Citation(
                document_id=chunk.document_id,
                chunk_id=chunk.id,
                company=chunk.company,
                doc_type=chunk.doc_type,
                published_at=chunk.published_at,
                excerpt=excerpt,
                page=chunk.page,
                url=chunk.metadata.get("url", ""),
            )
            citations.append(citation)

            block = (
                f"[Evidence {i}] doc={chunk.document_id} company={chunk.company} "
                f"type={chunk.doc_type} score={result.score:.4f}\n{chunk.text}\n"
            )
            if total + len(block) > max_chars:
                break
            parts.append(block)
            total += len(block)

        return "\n---\n".join(parts), citations
