from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from legacy_retrieval.config import get_settings
from legacy_retrieval.indexing.indexer import DocumentIndexer
from legacy_retrieval.models import QueryResponse
from legacy_retrieval.pipeline import RetrievalPipeline
from legacy_retrieval.structured.market_share import get_market_share_report

app = FastAPI(
    title="Legacy Capital Retrieval API",
    description="Research platform for equities document retrieval",
    version="0.1.0",
)

_pipeline: RetrievalPipeline | None = None


def get_pipeline() -> RetrievalPipeline:
    global _pipeline
    if _pipeline is None:
        settings = get_settings()
        indexer = DocumentIndexer(settings)
        state_dir = settings.processed_data_dir / "index_state"
        if state_dir.exists():
            indexer.load_state(state_dir)
        _pipeline = RetrievalPipeline(indexer, settings)
    return _pipeline


class QueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=10, ge=1, le=50)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/query", response_model=QueryResponse)
def query(request: QueryRequest) -> QueryResponse:
    pipeline = get_pipeline()
    if not pipeline.indexer.chunks:
        raise HTTPException(status_code=503, detail="Index not loaded. Run ingestion and indexing first.")
    return pipeline.query(request.question, top_k=request.top_k)


@app.get("/market-share/{institution}")
def market_share(institution: str) -> dict:
    return get_market_share_report(institution)
