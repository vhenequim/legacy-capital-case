from abc import ABC, abstractmethod
from datetime import datetime

from legacy_retrieval.models import Document


class BaseFetcher(ABC):
    source: str

    @abstractmethod
    def fetch(
        self,
        company: str,
        since: datetime | None = None,
        until: datetime | None = None,
        **kwargs: object,
    ) -> list[Document]:
        """Fetch documents from the source for a given company."""

    def save_raw(self, document: Document, raw_dir: str) -> None:
        """Optional hook to persist raw bytes; subclasses may override."""
