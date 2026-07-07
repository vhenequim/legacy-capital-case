import json
from datetime import datetime
from pathlib import Path

import httpx

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.ingestion.base import BaseFetcher
from legacy_retrieval.models import DocType, Document
from legacy_retrieval.parsing.html import parse_html
from legacy_retrieval.parsing.pdf import parse_pdf_bytes

# Configurable RI endpoints per company
RI_CONFIG: dict[str, dict[str, str]] = {
    "MSFT": {
        "earnings_url": "https://www.microsoft.com/en-us/investor/earnings",
        "base_url": "https://www.microsoft.com",
    },
    "NVDA": {
        "earnings_url": "https://investor.nvidia.com/financial-info/financial-reports/",
        "base_url": "https://investor.nvidia.com",
    },
    "ITUB4": {
        "earnings_url": "https://www.itau.com.br/relacoes-com-investidores/",
        "base_url": "https://www.itau.com.br",
    },
}


class InvestorRelationsFetcher(BaseFetcher):
    source = "investor_relations"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(
            headers={"User-Agent": self.settings.sec_user_agent},
            timeout=60.0,
            follow_redirects=True,
        )

    def fetch(
        self,
        company: str,
        since: datetime | None = None,
        until: datetime | None = None,
        **kwargs: object,
    ) -> list[Document]:
        return self._fetch_from_cache(company)

    def _fetch_from_cache(self, company: str) -> list[Document]:
        cache_dir = self.settings.raw_data_dir / "ri" / company.lower()
        if not cache_dir.exists():
            return []
        docs: list[Document] = []
        for path in cache_dir.glob("*.json"):
            docs.append(Document.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        return docs

    def ingest_url(
        self,
        company: str,
        url: str,
        title: str,
        doc_type: DocType = DocType.EARNINGS_RELEASE,
        published_at: datetime | None = None,
    ) -> Document:
        response = self._client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "pdf" in content_type or url.lower().endswith(".pdf"):
            content = parse_pdf_bytes(response.content)
        else:
            content = parse_html(response.text)

        doc_id = f"ri_{company.lower()}_{hash(url) % 10**10}"
        doc = Document(
            id=doc_id,
            source=self.source,
            company=company.upper(),
            doc_type=doc_type,
            published_at=published_at or datetime.utcnow(),
            title=title,
            url=url,
            content=content,
            metadata={"url": url},
        )

        out_dir = self.settings.raw_data_dir / "ri" / company.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{doc_id}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        return doc

    def ingest_local(
        self,
        company: str,
        file_path: Path,
        title: str,
        doc_type: DocType = DocType.EARNINGS_RELEASE,
        published_at: datetime | None = None,
    ) -> Document:
        suffix = file_path.suffix.lower()
        if suffix == ".pdf":
            content = parse_pdf_bytes(file_path.read_bytes())
        else:
            content = parse_html(file_path.read_text(encoding="utf-8", errors="ignore"))

        doc_id = f"ri_{company.lower()}_{file_path.stem}"
        doc = Document(
            id=doc_id,
            source=self.source,
            company=company.upper(),
            doc_type=doc_type,
            published_at=published_at or datetime.fromtimestamp(file_path.stat().st_mtime),
            title=title,
            content=content,
            metadata={"file": str(file_path)},
        )

        out_dir = self.settings.raw_data_dir / "ri" / company.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{doc_id}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        return doc
