from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.models import Citation, QueryResponse, RetrievedChunk
from legacy_retrieval.retrieval.evidence import EvidenceBuilder

REFUSAL_MESSAGE = "Não encontrei essa informação na base."

SYSTEM_PROMPT = """You are a research assistant for equity analysts.
Answer ONLY using the provided evidence. Never use outside knowledge.
If evidence is insufficient, respond exactly: "Não encontrei essa informação na base."
Always cite sources using [Evidence N] references from the context.
Be concise and factual."""


class GroundedGenerator:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.evidence_builder = EvidenceBuilder()

    def generate(
        self,
        question: str,
        results: list[RetrievedChunk],
    ) -> QueryResponse:
        if not results:
            return QueryResponse(
                question=question,
                answer=REFUSAL_MESSAGE,
                citations=[],
                confidence=0.0,
                refused=True,
            )

        if self._should_refuse(results):
            max_score = max(r.score for r in results) if results else 0.0
            return QueryResponse(
                question=question,
                answer=REFUSAL_MESSAGE,
                citations=[],
                confidence=max_score,
                refused=True,
            )

        max_score = max(r.score for r in results)

        context, citations = self.evidence_builder.build(results)

        if self.settings.llm_provider == "openai" and self.settings.openai_api_key:
            answer = self._generate_openai(question, context)
        elif self.settings.llm_provider == "ollama":
            answer = self._generate_ollama(question, context)
            if answer == REFUSAL_MESSAGE and results:
                answer = self._generate_extractive(question, results, citations)
        else:
            answer = self._generate_extractive(question, results, citations)

        refused = REFUSAL_MESSAGE in answer
        confidence = min(1.0, max_score) if not refused else 0.0

        return QueryResponse(
            question=question,
            answer=answer,
            citations=citations if not refused else [],
            confidence=confidence,
            refused=refused,
        )

    def _should_refuse(self, results: list[RetrievedChunk]) -> bool:
        if not results:
            return True
        top = results[0]
        if top.source == "rerank":
            return top.score < -8.0
        return top.score < 0.008

    def _generate_openai(self, question: str, context: str) -> str:
        from openai import OpenAI

        client = OpenAI(api_key=self.settings.openai_api_key)
        response = client.chat.completions.create(
            model=self.settings.openai_model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": f"Question: {question}\n\nEvidence:\n{context}",
                },
            ],
            temperature=0.0,
        )
        return response.choices[0].message.content or REFUSAL_MESSAGE

    def _generate_ollama(self, question: str, context: str) -> str:
        import httpx

        try:
            response = httpx.post(
                f"{self.settings.ollama_base_url}/api/chat",
                json={
                    "model": self.settings.ollama_model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": f"Question: {question}\n\nEvidence:\n{context}",
                        },
                    ],
                    "stream": False,
                    "options": {"temperature": 0.0},
                },
                timeout=120.0,
            )
            response.raise_for_status()
            return response.json().get("message", {}).get("content", REFUSAL_MESSAGE)
        except Exception:
            return REFUSAL_MESSAGE

    def _generate_extractive(
        self,
        question: str,
        results: list[RetrievedChunk],
        citations: list[Citation],
    ) -> str:
        """Mock/local generator: synthesize from top evidence snippets."""
        if not results:
            return REFUSAL_MESSAGE

        top = results[0]
        snippet = top.chunk.text[:400].strip()
        parts = ["Com base nas evidências indexadas [Evidence 1]:"]
        parts.append(snippet)

        if len(results) > 1:
            parts.append(
                f"\nInformação adicional de [Evidence 2] ({results[1].chunk.company}, "
                f"{results[1].chunk.doc_type}): {results[1].chunk.text[:200].strip()}..."
            )

        return "\n".join(parts)
