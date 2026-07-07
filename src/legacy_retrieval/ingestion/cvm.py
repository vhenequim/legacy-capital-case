import json
from datetime import datetime
from pathlib import Path

import httpx

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.ingestion.base import BaseFetcher
from legacy_retrieval.models import DocType, Document
from legacy_retrieval.parsing.html import parse_html

# CVM company codes (example mappings)
CVM_COMPANY_CODES: dict[str, str] = {
    "ITUB4": "1023",
    "BBDC4": "906",
    "SANB11": "20532",
    "BBAS3": "10261",
    "NUBR33": "21750",
}


class CvmFetcher(BaseFetcher):
  source = "cvm"

  BASE_URL = "https://www.rad.cvm.gov.br/ENET/frmDownloadDocumento.aspx"

  def __init__(self, settings: Settings | None = None) -> None:
      self.settings = settings or get_settings()
      self._client = httpx.Client(timeout=60.0, follow_redirects=True)

  def fetch(
      self,
      company: str,
      since: datetime | None = None,
      until: datetime | None = None,
      **kwargs: object,
  ) -> list[Document]:
      code = CVM_COMPANY_CODES.get(company.upper())
      if not code:
          return self._fetch_from_cache(company)

      # CVM API via consulta externa (simplified - uses local cache when API unavailable)
      return self._fetch_from_cache(company)

  def _fetch_from_cache(self, company: str) -> list[Document]:
      cache_dir = self.settings.raw_data_dir / "cvm" / company.lower()
      if not cache_dir.exists():
          return []
      docs: list[Document] = []
      for path in cache_dir.glob("*.json"):
          docs.append(Document.model_validate(json.loads(path.read_text(encoding="utf-8"))))
      return docs

  def ingest_local_file(
      self,
      company: str,
      file_path: Path,
      doc_type: DocType = DocType.FILING,
      published_at: datetime | None = None,
  ) -> Document:
      suffix = file_path.suffix.lower()
      if suffix == ".pdf":
          from legacy_retrieval.parsing.pdf import parse_pdf_file

          content = parse_pdf_file(str(file_path))
      elif suffix in {".html", ".htm"}:
          content = parse_html(file_path.read_text(encoding="utf-8", errors="ignore"))
      else:
          content = file_path.read_text(encoding="utf-8", errors="ignore")

      published = published_at or datetime.fromtimestamp(file_path.stat().st_mtime)
      doc_id = f"cvm_{company.lower()}_{file_path.stem}"

      doc = Document(
          id=doc_id,
          source=self.source,
          company=company.upper(),
          doc_type=doc_type,
          published_at=published,
          title=file_path.stem,
          content=content,
          metadata={"file": str(file_path)},
      )

      out_dir = self.settings.raw_data_dir / "cvm" / company.lower()
      out_dir.mkdir(parents=True, exist_ok=True)
      (out_dir / f"{doc_id}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")
      return doc
