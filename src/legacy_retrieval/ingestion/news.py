import hashlib
from datetime import datetime

import feedparser
import httpx

from legacy_retrieval.config import Settings, get_settings
from legacy_retrieval.ingestion.base import BaseFetcher
from legacy_retrieval.models import DocType, Document
from legacy_retrieval.parsing.html import parse_html

YAHOO_FEED_TEMPLATE = (
    "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}&region=US&lang=en-US"
)


def default_feeds(ticker: str) -> list[str]:
    return [YAHOO_FEED_TEMPLATE.format(ticker=ticker.upper())]


class NewsFetcher(BaseFetcher):
    source = "news"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = httpx.Client(timeout=30.0, follow_redirects=True)

    def fetch(
        self,
        company: str,
        since: datetime | None = None,
        until: datetime | None = None,
        feeds: list[str] | None = None,
        max_items: int = 20,
        **kwargs: object,
    ) -> list[Document]:
        feed_urls = feeds or default_feeds(company)
        documents: list[Document] = []

        for feed_url in feed_urls:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:max_items]:
                published = datetime.utcnow()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])

                if since and published < since:
                    continue
                if until and published > until:
                    continue

                summary = getattr(entry, "summary", "") or ""
                title = getattr(entry, "title", "News")
                link = getattr(entry, "link", "")

                content = summary
                if link:
                    try:
                        resp = self._client.get(link)
                        if resp.status_code == 200:
                            content = parse_html(resp.text)[:5000]
                    except Exception:
                        pass

                digest = hashlib.sha256((link or title).encode()).hexdigest()[:12]
                doc_id = f"news_{company.lower()}_{digest}"
                documents.append(
                    Document(
                        id=doc_id,
                        source=self.source,
                        company=company.upper(),
                        doc_type=DocType.NEWS,
                        published_at=published,
                        title=title,
                        url=link,
                        content=content or summary,
                        metadata={"feed": feed_url},
                    )
                )

        return documents
