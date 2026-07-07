import hashlib
import re
from datetime import datetime
from pathlib import Path

import httpx
from dateutil import parser as date_parser
from tenacity import retry, stop_after_attempt, wait_exponential

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.ingestion.base import BaseFetcher
from legacy_retrieval.models import DocType, Document
from legacy_retrieval.parsing.html import parse_html
from legacy_retrieval.parsing.pdf import parse_pdf_bytes

# SEC CIK lookup for common tickers used in cases
TICKER_CIK: dict[str, str] = {
    "MSFT": "0000789019",
    "AMZN": "0001018724",
    "GOOG": "0001652044",
    "GOOGL": "0001652044",
    "META": "0001326801",
    "NVDA": "0001045810",
    "ORCL": "0001341439",
    "CRWV": "0001769628",
    "NBIS": "0001513845",
    # Bancos brasileiros com ADR — 6-K/20-F contêm os earnings releases oficiais
    "NU": "0001691493",
    "ITUB": "0001132597",
    "BBD": "0001160330",
    "BSBR": "0001471055",
    "CRM": "0001108524",
    "NOW": "0001373715",
    "SAP": "0001000184",
    "HUBS": "0001404655",
    "NET": "0001477333",
    "DDOG": "0001561550",
    "SNOW": "0001640147",
    "AKAM": "0001086222",
    "PANW": "0001327567",
    "CRWD": "0001535527",
    "OKTA": "0001660134",
    "TEAM": "0001650372",
    "MNDY": "0001845338",
    "GTLB": "0001653482",
    "ZS": "0001713683",
}

FILING_TYPES = {"10-K", "10-Q", "8-K", "20-F", "6-K"}


class SecEdgarFetcher(BaseFetcher):
    source = "sec_edgar"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(
            headers={"User-Agent": self.settings.sec_user_agent},
            timeout=60.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SecEdgarFetcher":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _cik(self, company: str) -> str:
        key = company.upper().strip()
        if key in TICKER_CIK:
            return TICKER_CIK[key]
        if key.isdigit():
            return key.zfill(10)
        raise ValueError(f"Unknown ticker/CIK for SEC EDGAR: {company}")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def _get(self, url: str) -> httpx.Response:
        response = self._client.get(url)
        response.raise_for_status()
        return response

    def _submissions(self, cik: str) -> dict:
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        return self._get(url).json()

    def _filing_documents(self, cik: str, accession: str, primary_doc: str, form: str = "") -> str:
        accession_no_dash = accession.replace("-", "")
        base = f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession_no_dash}"
        parts = [self._fetch_and_parse(f"{base}/{primary_doc}")]

        # 8-K/6-K: o documento principal é só a capa; o earnings release
        # real está nos exhibits EX-99.*
        if form in {"8-K", "6-K"}:
            parts.extend(self._fetch_exhibits(base, primary_doc))

        return "\n\n".join(p for p in parts if p)

    # Artefatos XBRL/viewer que não são exhibits de conteúdo
    _EXHIBIT_SKIP = re.compile(
        r"(^R\d+\.htm$)|(-index)|(FilingSummary)|(_lab|_pre|_cal|_def|_htm)", re.I
    )

    def _fetch_exhibits(self, base: str, primary_doc: str, max_exhibits: int = 3) -> list[str]:
        """Baixa os maiores exhibits HTML/PDF do filing (press release, comentário do CFO).

        Nomes de exhibit variam por empresa (ex99-1.htm, q1fy27pr.htm), então o
        filtro é por extensão + tamanho, excluindo artefatos XBRL.
        """
        try:
            index = self._get(f"{base}/index.json").json()
        except Exception:
            return []

        candidates: list[tuple[int, str]] = []
        for item in index.get("directory", {}).get("item", []):
            name = item.get("name", "")
            if name == primary_doc:
                continue
            if not name.lower().endswith((".htm", ".html", ".pdf")):
                continue
            if self._EXHIBIT_SKIP.search(name):
                continue
            size = int(item.get("size") or 0)
            if size < 5_000:
                continue
            candidates.append((size, name))

        candidates.sort(reverse=True)
        parts: list[str] = []
        for _, name in candidates[:max_exhibits]:
            try:
                parts.append(self._fetch_and_parse(f"{base}/{name}"))
            except Exception:
                continue
        return parts

    def _fetch_and_parse(self, url: str) -> str:
        response = self._get(url)
        lower = url.lower()
        if lower.endswith(".pdf"):
            return parse_pdf_bytes(response.content)
        if lower.endswith((".htm", ".html")):
            return parse_html(response.text)
        return response.text

    def fetch(
        self,
        company: str,
        since: datetime | None = None,
        until: datetime | None = None,
        filing_types: set[str] | None = None,
        max_filings: int = 50,
        **kwargs: object,
    ) -> list[Document]:
        cik = self._cik(company)
        allowed = filing_types or FILING_TYPES
        submissions = self._submissions(cik)
        company_name = submissions.get("name", company)

        recent = submissions.get("filings", {}).get("recent", {})
        documents: list[Document] = []

        forms = recent.get("form", [])
        dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])

        for form, filing_date, accession, primary_doc in zip(
            forms, dates, accessions, primary_docs, strict=False
        ):
            if len(documents) >= max_filings:
                break
            if form not in allowed:
                continue

            published = date_parser.parse(filing_date)
            if since and published < since:
                continue
            if until and published > until:
                continue

            try:
                content = self._filing_documents(cik, accession, primary_doc, form)
            except Exception:
                continue

            content = re.sub(r"\s+", " ", content).strip()
            if len(content) < 100:
                continue

            doc_id = f"sec_{cik}_{accession.replace('-', '')}"
            accession_no_dash = accession.replace("-", "")
            url = (
                f"https://www.sec.gov/Archives/edgar/data/"
                f"{int(cik)}/{accession_no_dash}/{primary_doc}"
            )

            documents.append(
                Document(
                    id=doc_id,
                    source=self.source,
                    company=company.upper(),
                    doc_type=DocType.FILING,
                    published_at=published,
                    title=f"{company_name} {form} {filing_date}",
                    url=url,
                    content=content[:500_000],
                    metadata={
                        "cik": cik,
                        "form": form,
                        "accession": accession,
                        "primary_document": primary_doc,
                    },
                )
            )

        return documents

    def fetch_and_cache(
        self,
        company: str,
        since: datetime | None = None,
        raw_dir: Path | None = None,
    ) -> list[Document]:
        docs = self.fetch(company=company, since=since)
        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            for doc in docs:
                path = raw_dir / f"{doc.id}.json"
                path.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        return docs


def document_id_from_content(source: str, company: str, content: str) -> str:
    digest = hashlib.sha256(content.encode()).hexdigest()[:16]
    return f"{source}_{company.lower()}_{digest}"
