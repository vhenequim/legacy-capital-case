"""CVM — ingestão real via Portal de Dados Abertos (documentos IPE).

Fonte: https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/
O CSV anual lista todos os documentos entregues (press-releases de resultado,
fatos relevantes, apresentações), com link de download no rad.cvm.gov.br.
"""

import csv
import hashlib
import io
import zipfile
from datetime import datetime
from pathlib import Path

import httpx
from dateutil import parser as date_parser

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.ingestion.base import BaseFetcher
from legacy_retrieval.models import DocType, Document
from legacy_retrieval.parsing.html import parse_html
from legacy_retrieval.parsing.pdf import parse_pdf_bytes

IPE_URL_TEMPLATE = "https://dados.cvm.gov.br/dados/CIA_ABERTA/DOC/IPE/DADOS/ipe_cia_aberta_{year}.zip"

# Código CVM oficial por ticker (verificado no próprio CSV do portal)
CVM_COMPANY_CODES: dict[str, tuple[str, str]] = {
    "ITUB4": ("19348", "ITAÚ UNIBANCO HOLDING"),
    "BBDC4": ("906", "BANCO BRADESCO"),
    "SANB11": ("20532", "BANCO SANTANDER (BRASIL)"),
    "BBAS3": ("1023", "BANCO DO BRASIL"),
}


def _relevant(row: dict) -> bool:
    categoria = (row.get("Categoria") or "").strip()
    tipo = (row.get("Tipo") or "").strip()
    assunto = (row.get("Assunto") or "").strip().lower()

    if categoria.startswith("Dados Econ"):
        return True
    if categoria.startswith("Fato Relevante"):
        return True
    if categoria.startswith("Comunicado ao Mercado"):
        return "esultado" in assunto or "presenta" in tipo.lower()
    return False


def _doc_type(row: dict) -> DocType:
    categoria = (row.get("Categoria") or "").strip()
    tipo = (row.get("Tipo") or "").strip().lower()
    if "press-release" in tipo:
        return DocType.EARNINGS_RELEASE
    if "presenta" in tipo:
        return DocType.PRESENTATION
    if categoria.startswith("Fato Relevante"):
        return DocType.NEWS
    return DocType.FILING


class CvmFetcher(BaseFetcher):
    source = "cvm"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(timeout=90.0, follow_redirects=True)

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "CvmFetcher":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _ipe_rows(self, year: int) -> list[dict]:
        """Baixa (com cache) o índice IPE de um ano e devolve as linhas do CSV."""
        cache = self.settings.raw_data_dir / "cvm" / f"ipe_cia_aberta_{year}.zip"
        if not cache.exists():
            response = self._client.get(IPE_URL_TEMPLATE.format(year=year))
            response.raise_for_status()
            cache.parent.mkdir(parents=True, exist_ok=True)
            cache.write_bytes(response.content)

        with zipfile.ZipFile(cache) as z:
            name = z.namelist()[0]
            with z.open(name) as f:
                reader = csv.DictReader(
                    io.TextIOWrapper(f, encoding="latin-1"), delimiter=";"
                )
                return list(reader)

    def fetch(
        self,
        company: str,
        since: datetime | None = None,
        until: datetime | None = None,
        max_docs: int = 25,
        **kwargs: object,
    ) -> list[Document]:
        entry = CVM_COMPANY_CODES.get(company.upper())
        if not entry:
            raise ValueError(
                f"Empresa sem código CVM mapeado: {company}. "
                f"Disponíveis: {sorted(CVM_COMPANY_CODES)}"
            )
        codigo_cvm, _name = entry

        since = since or datetime(2024, 1, 1)
        until = until or datetime.utcnow()

        candidates: list[dict] = []
        for year in range(since.year, until.year + 1):
            try:
                rows = self._ipe_rows(year)
            except httpx.HTTPError:
                continue
            for row in rows:
                if (row.get("Codigo_CVM") or "").strip() != codigo_cvm:
                    continue
                if not _relevant(row):
                    continue
                try:
                    delivered = date_parser.parse(row["Data_Entrega"])
                except Exception:
                    continue
                if delivered < since or delivered > until:
                    continue
                row["_delivered"] = delivered
                candidates.append(row)

        # Mais recentes primeiro, limitado para não sobrecarregar o rad.cvm
        candidates.sort(key=lambda r: r["_delivered"], reverse=True)

        documents: list[Document] = []
        for row in candidates:
            if len(documents) >= max_docs:
                break
            doc = self._download_row(company.upper(), row)
            if doc is not None:
                documents.append(doc)
                self._save_to_cache(doc)
        return documents

    def _download_row(self, ticker: str, row: dict) -> Document | None:
        link = (row.get("Link_Download") or "").strip()
        if not link:
            return None
        try:
            response = self._client.get(link)
            response.raise_for_status()
        except httpx.HTTPError:
            return None

        content_type = (response.headers.get("content-type") or "").lower()
        try:
            if "pdf" in content_type or response.content[:4] == b"%PDF":
                content = parse_pdf_bytes(response.content)
            else:
                content = parse_html(response.text)
        except Exception:
            return None

        if len(content.strip()) < 200:
            return None

        digest = hashlib.sha256(link.encode()).hexdigest()[:12]
        assunto = (row.get("Assunto") or "").strip()
        categoria = (row.get("Categoria") or "").strip()
        title = f"{row.get('Nome_Companhia', ticker)} — {categoria}"
        if assunto:
            title += f": {assunto}"

        return Document(
            id=f"cvm_{ticker.lower()}_{digest}",
            source=self.source,
            company=ticker,
            doc_type=_doc_type(row),
            published_at=row["_delivered"],
            title=title[:200],
            url=link,
            content=content[:500_000],
            metadata={
                "codigo_cvm": row.get("Codigo_CVM", ""),
                "categoria": categoria,
                "tipo": (row.get("Tipo") or "").strip(),
                "assunto": assunto,
                "data_referencia": row.get("Data_Referencia", ""),
            },
        )

    def _save_to_cache(self, doc: Document) -> None:
        out_dir = self.settings.raw_data_dir / "cvm" / doc.company.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{doc.id}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")

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
        self._save_to_cache(doc)
        return doc
