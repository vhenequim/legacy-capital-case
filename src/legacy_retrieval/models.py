from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class DocType(StrEnum):
    EARNINGS_RELEASE = "earnings_release"
    TRANSCRIPT = "transcript"
    FILING = "filing"
    NEWS = "news"
    PRESENTATION = "presentation"
    STRUCTURED = "structured"


class Document(BaseModel):
    id: str
    source: str
    company: str
    doc_type: DocType | str
    published_at: datetime
    content: str
    title: str = ""
    url: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class Chunk(BaseModel):
    id: str
    document_id: str
    text: str
    chunk_index: int
    page: int | None = None
    company: str = ""
    doc_type: str = ""
    published_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedChunk(BaseModel):
    chunk: Chunk
    score: float
    source: str = "hybrid"


class Citation(BaseModel):
    document_id: str
    chunk_id: str
    company: str
    doc_type: str
    published_at: datetime | None
    excerpt: str
    page: int | None = None
    url: str = ""


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.0
    refused: bool = False
    structured_data: dict[str, Any] | None = None


class EvalQuestion(BaseModel):
    id: str
    question: str
    expected_doc_ids: list[str] = Field(default_factory=list)
    expected_chunk_ids: list[str] = Field(default_factory=list)
    category: str
    answerable: bool = True
    case: str = ""
    notes: str = ""
