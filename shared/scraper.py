"""
Base scraper class with Data Toolkit pipeline integration.
Every service inherits this → scrape → clean → export.
"""
import json
import csv
import hashlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from .proxy_client import ProxiesSXClient, X402Config


@dataclass
class ScrapedItem:
    """Normalized scraped item with Data Toolkit metadata."""
    source_url: str
    scraped_at: str  # ISO 8601
    data: dict
    content_hash: str = ""
    confidence: float = 1.0

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = hashlib.sha256(
                json.dumps(self.data, sort_keys=True).encode()
            ).hexdigest()
        if not self.scraped_at:
            self.scraped_at = datetime.now(timezone.utc).isoformat()


@dataclass
class ScraperResult:
    """Result of a scrape operation with Data Toolkit-processed output."""
    items: list[ScrapedItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    proxy_country: str = "US"
    duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        total = len(self.items) + len(self.errors)
        return len(self.items) / total if total > 0 else 1.0

    def deduplicate(self) -> "ScraperResult":
        """Remove duplicate items by content hash."""
        seen = set()
        unique = []
        for item in self.items:
            if item.content_hash not in seen:
                seen.add(item.content_hash)
                unique.append(item)
        self.items = unique
        return self

    def filter_nulls(self) -> "ScraperResult":
        """Remove items with empty/null data fields."""
        self.items = [
            item for item in self.items
            if item.data and any(v is not None and v != "" for v in item.data.values())
        ]
        return self

    def to_json(self, path: Optional[str] = None) -> str:
        """Export to JSON via Data Toolkit normalization."""
        output = [
            {
                "source_url": item.source_url,
                "scraped_at": item.scraped_at,
                "content_hash": item.content_hash,
                "confidence": item.confidence,
                **item.data,
            }
            for item in self.items
        ]
        json_str = json.dumps(output, indent=2, ensure_ascii=False)
        if path:
            with open(path, "w") as f:
                f.write(json_str)
        return json_str

    def to_csv(self, path: str) -> str:
        """Export to CSV with automatic column detection."""
        if not self.items:
            return ""
        all_keys = set()
        for item in self.items:
            all_keys.update(item.data.keys())
        fieldnames = ["source_url", "scraped_at", "content_hash"] + sorted(all_keys)

        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for item in self.items:
                row = {
                    "source_url": item.source_url,
                    "scraped_at": item.scraped_at,
                    "content_hash": item.content_hash,
                    **item.data,
                }
                writer.writerow(row)
        return path


class BaseScraper(ABC):
    """Abstract base for all Proxies.sx service scrapers."""

    def __init__(self, country: str = "US", proxy_config: Optional[X402Config] = None):
        self.country = country
        self.proxy_client = ProxiesSXClient(proxy_config or X402Config())

    @abstractmethod
    async def scrape(self, **kwargs) -> ScraperResult:
        """Implement the scraping logic."""
        ...

    @abstractmethod
    def schema(self) -> dict:
        """Return JSON Schema for this service's output."""
        ...

    async def run(self, **kwargs) -> ScraperResult:
        """Full pipeline: scrape → deduplicate → filter nulls → ready for export."""
        import time
        t0 = time.monotonic()
        try:
            result = await self.scrape(**kwargs)
        except Exception as e:
            result = ScraperResult(errors=[str(e)])
        result.duration_ms = (time.monotonic() - t0) * 1000
        result.deduplicate()
        result.filter_nulls()
        return result

    async def close(self):
        await self.proxy_client.close()
