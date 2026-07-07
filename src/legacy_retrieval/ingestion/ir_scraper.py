"""
Generic Investor Relations scraper driven by config/ir_sites.yaml.

Strategy: crawl seed pages, discover PDF/HTML links matching patterns,
download and normalize into Document objects. No per-site hardcoded parsers.
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.ingestion.base import BaseFetcher
from legacy_retrieval.models import DocType, Document
from legacy_retrieval.parsing.html import parse_html
from legacy_retrieval.parsing.pdf import parse_pdf_bytes

CONFIG_PATH = Path(__file__).resolve().parents[3] / "config" / "ir_sites.yaml"

SKIP_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".svg", ".css", ".js", ".zip", ".mp4", ".mp3"}

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class IrSiteConfig:
    def __init__(self, ticker: str, raw: dict) -> None:
        self.ticker = ticker.upper()
        self.base_url: str = raw["base_url"]
        self.seed_urls: list[str] = raw.get("seed_urls", [])
        self.allowed_domains: list[str] = raw.get("allowed_domains", [])
        self.link_patterns: list[str] = raw.get("link_patterns", [])
        self.max_documents: int = raw.get("max_documents", 20)


def load_ir_configs(path: Path | None = None) -> dict[str, IrSiteConfig]:
    config_path = path or CONFIG_PATH
    if not config_path.exists():
        return {}
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return {ticker: IrSiteConfig(ticker, data) for ticker, data in raw.items()}


class IrScraper(BaseFetcher):
    source = "investor_relations"

    def __init__(self, settings: Settings | None = None, config_path: Path | None = None) -> None:
        self.settings = settings or get_settings()
        self.configs = load_ir_configs(config_path)
        self._client = httpx.Client(
            headers=BROWSER_HEADERS,
            timeout=60.0,
            follow_redirects=True,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> IrScraper:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def fetch(
        self,
        company: str,
        since: datetime | None = None,
        until: datetime | None = None,
        **kwargs: object,
    ) -> list[Document]:
        config = self.configs.get(company.upper())
        if not config:
            return self._load_cache(company)

        discovered = self._discover_links(config)
        documents: list[Document] = []

        for url, title in discovered[: config.max_documents]:
            try:
                doc = self._download_document(config.ticker, url, title)
            except Exception:
                continue

            if since and doc.published_at < since:
                continue
            if until and doc.published_at > until:
                continue
            if len(doc.content.strip()) < 80:
                continue

            documents.append(doc)
            self._save_to_cache(doc)

        return documents

    def _discover_links(self, config: IrSiteConfig) -> list[tuple[str, str]]:
        seen: set[str] = set()
        results: list[tuple[str, str]] = []
        queue: list[str] = list(config.seed_urls)
        visited_pages: set[str] = set()

        while queue and len(visited_pages) < 8:
            page_url = queue.pop(0)
            if page_url in visited_pages:
                continue
            visited_pages.add(page_url)

            try:
                response = self._client.get(page_url)
                if response.status_code >= 400:
                    continue
            except Exception:
                continue

            soup = BeautifulSoup(response.text, "lxml")
            for anchor in soup.find_all("a", href=True):
                href = anchor["href"].strip()
                if not href or href.startswith("#") or href.startswith("mailto:"):
                    continue

                full_url = urljoin(page_url, href)
                parsed = urlparse(full_url)

                if parsed.scheme not in {"http", "https"}:
                    continue

                title = anchor.get_text(strip=True) or parsed.path.split("/")[-1]

                # Follow intermediate pages (e.g. aka.ms redirects, earnings detail pages)
                if (
                    self._domain_allowed(parsed.netloc, config.allowed_domains)
                    and full_url not in visited_pages
                    and not any(parsed.path.lower().endswith(ext) for ext in SKIP_EXTENSIONS)
                    and self._matches_patterns(full_url, config.link_patterns)
                    and not full_url.lower().endswith(".pdf")
                    and len(queue) < 12
                ):
                    queue.append(full_url)

                if not self._domain_allowed(parsed.netloc, config.allowed_domains):
                    # Allow known redirect shorteners used by IR sites
                    if not any(d in parsed.netloc for d in ("aka.ms", "q4cdn.com")):
                        continue
                if any(parsed.path.lower().endswith(ext) for ext in SKIP_EXTENSIONS):
                    continue
                if not self._matches_patterns(full_url, config.link_patterns):
                    continue
                if full_url in seen:
                    continue

                seen.add(full_url)
                results.append((full_url, title))

        return results

    @staticmethod
    def _domain_allowed(netloc: str, allowed: list[str]) -> bool:
        host = netloc.lower().removeprefix("www.")
        return any(host == d or host.endswith(f".{d}") for d in allowed)

    @staticmethod
    def _matches_patterns(url: str, patterns: list[str]) -> bool:
        url_lower = url.lower()
        return any(p.lower() in url_lower for p in patterns)

    def _download_document(self, ticker: str, url: str, title: str) -> Document:
        response = self._client.get(url)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "").lower()
        is_pdf = "pdf" in content_type or url.lower().endswith(".pdf")

        if is_pdf:
            content = parse_pdf_bytes(response.content)
            doc_type = DocType.PRESENTATION if "presentation" in url.lower() else DocType.EARNINGS_RELEASE
        else:
            content = parse_html(response.text)
            doc_type = DocType.EARNINGS_RELEASE
            if "transcript" in url.lower() or "transcript" in title.lower():
                doc_type = DocType.TRANSCRIPT
            elif "presentation" in url.lower() or "presentation" in title.lower():
                doc_type = DocType.PRESENTATION

        published = self._guess_date(url, title, response)
        doc_id = f"ri_{ticker.lower()}_{hashlib.sha256(url.encode()).hexdigest()[:12]}"

        return Document(
            id=doc_id,
            source=self.source,
            company=ticker,
            doc_type=doc_type,
            published_at=published,
            title=title[:200] or url,
            url=url,
            content=content[:500_000],
            metadata={"url": url, "content_type": content_type},
        )

    @staticmethod
    def _guess_date(url: str, title: str, response: httpx.Response) -> datetime:
        for candidate in (url, title):
            match = re.search(r"20\d{2}[-_/]?(?:0[1-9]|1[0-2])", candidate)
            if match:
                try:
                    return date_parser.parse(match.group(0), fuzzy=True)
                except Exception:
                    pass
            match = re.search(r"Q[1-4][\s-]*20\d{2}", candidate, re.I)
            if match:
                try:
                    return date_parser.parse(match.group(0).replace("Q", "Q "), fuzzy=True)
                except Exception:
                    pass

        last_modified = response.headers.get("last-modified")
        if last_modified:
            try:
                return date_parser.parse(last_modified)
            except Exception:
                pass

        return datetime.utcnow()

    def _save_to_cache(self, doc: Document) -> None:
        out_dir = self.settings.raw_data_dir / "ri" / doc.company.lower()
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / f"{doc.id}.json").write_text(doc.model_dump_json(indent=2), encoding="utf-8")

    def _load_cache(self, company: str) -> list[Document]:
        cache_dir = self.settings.raw_data_dir / "ri" / company.lower()
        if not cache_dir.exists():
            return []
        docs: list[Document] = []
        for path in cache_dir.glob("*.json"):
            docs.append(Document.model_validate_json(path.read_text(encoding="utf-8")))
        return docs
