from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = ""
    embedding_provider: str = "local"
    llm_provider: str = "local"
    openai_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"

    # Groq (free tier, OpenAI-compatible API) — set LLM_PROVIDER=groq
    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Ollama (free local LLM) — set LLM_PROVIDER=ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "legacy_documents"

    database_url: str = "postgresql://legacy:legacy@localhost:5432/legacy_retrieval"

    data_dir: Path = Path("./data")
    raw_data_dir: Path = Path("./data/raw")
    processed_data_dir: Path = Path("./data/processed")

    # Em CARACTERES (~300 tokens). Chunks maiores preservam contexto de
    # tabelas financeiras e reduzem o volume de embeddings.
    chunk_size: int = 1800
    chunk_overlap: int = 200
    retrieval_top_k: int = 20
    rerank_top_k: int = 10
    evidence_threshold: float = 0.3

    sec_user_agent: str = "LegacyCapitalResearch contact@example.com"

    @property
    def qdrant_url(self) -> str:
        return f"http://{self.qdrant_host}:{self.qdrant_port}"


def get_settings() -> Settings:
    return Settings()
