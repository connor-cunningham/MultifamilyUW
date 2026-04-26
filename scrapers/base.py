"""Abstract base class for property scrapers."""
from abc import ABC, abstractmethod
from typing import Iterator

from models.property import Property


class BasePropertyScraper(ABC):
    """Each scraper must implement fetch() as a generator of Property objects."""

    source_name: str = "unknown"

    @abstractmethod
    def fetch(
        self,
        states: list[str],
        min_units: int = 3,
        max_units: int = 10,
        max_price: float = 2_000_000,
        max_results: int = 50,
    ) -> Iterator[Property]:
        """Yield Property objects matching the given filters."""
        ...
