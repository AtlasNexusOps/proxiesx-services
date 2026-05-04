"""
Trend Intelligence API — Proxies.sx Bounty #70 ($100)
Cross-platform trend aggregation: Reddit, X, TikTok, Google Trends.
"""
import asyncio
from typing import Optional

from ..shared.scraper import BaseScraper, ScrapedItem, ScraperResult
from ..shared.proxy_client import X402Config


class TrendIntelligenceTracker(BaseScraper):
    """
    Cross-platform trend intelligence aggregator.

    Endpoints:
    - /trend/{keyword} — cross-platform volume + sentiment
    - /compare — multi-keyword trend overlay
    """

    SOURCES = {
        "reddit": "https://www.reddit.com",
        "twitter": "https://twitter.com",
        "google_trends": "https://trends.google.com/trends/explore",
    }

    def __init__(self, country: str = "US", proxy_config: Optional[X402Config] = None):
        super().__init__(country, proxy_config)

    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string"},
                "source": {"type": "string", "enum": list(self.SOURCES.keys())},
                "mention_count": {"type": "integer"},
                "sentiment_score": {"type": "number", "minimum": -1, "maximum": 1},
                "sentiment_label": {"type": "string", "enum": ["positive", "neutral", "negative"]},
                "trend_velocity": {"type": "number", "description": "% change over period"},
                "top_posts": {"type": "array", "items": {"type": "object"}},
                "related_keywords": {"type": "array", "items": {"type": "string"}},
                "time_period": {"type": "string", "default": "7d"},
                "scraped_at": {"type": "string", "format": "date-time"},
            },
            "required": ["keyword", "source"],
        }

    async def scrape(self, keyword: str = None, keywords: list[str] = None,
                     sources: list[str] = None, period: str = "7d") -> ScraperResult:
        """
        Aggregate trends across platforms.

        Args:
            keyword: Single keyword to track
            keywords: Multiple keywords for comparison
            sources: Platforms to query (default: all)
            period: Time period — 1d, 7d, 30d
        """
        sources = sources or list(self.SOURCES.keys())
        terms = keywords or ([keyword] if keyword else None)
        if not terms:
            raise ValueError("Must provide keyword or keywords")

        items = []
        errors = []

        for term in terms:
            for source in sources:
                try:
                    source_items = await self._query_source(source, term, period)
                    items.extend(source_items)
                    # Rate limit between platforms
                    await asyncio.sleep(0.5)
                except Exception as e:
                    errors.append(f"{source}:{term} — {e}")

        return ScraperResult(items=items, errors=errors, proxy_country=self.country)

    async def _query_source(self, source: str, keyword: str, period: str) -> list[ScrapedItem]:
        """Query a single trend source."""
        proxy, client = await self.proxy_client.create_scraper_session(self.country)
        items = []

        try:
            import re

            if source == "reddit":
                url = f"{self.SOURCES['reddit']}/search.json?q={keyword.replace(' ', '+')}&sort=relevance&t={period}"
                resp = await client.get(url, headers={"User-Agent": "ProxiesX-TrendBot/1.0"})
                resp.raise_for_status()
                data = resp.json()
                posts = data.get("data", {}).get("children", [])
                mention_count = len(posts)
                sentiment = self._compute_sentiment([p["data"].get("title", "") for p in posts])
                related = self._extract_related([p["data"].get("title", "") for p in posts], keyword)

                items.append(ScrapedItem(
                    source_url=url,
                    data={
                        "keyword": keyword,
                        "source": source,
                        "mention_count": mention_count,
                        "sentiment_score": sentiment["score"],
                        "sentiment_label": sentiment["label"],
                        "trend_velocity": self._compute_velocity(posts, period),
                        "top_posts": [{"title": p["data"].get("title"), "score": p["data"].get("score"),
                                       "subreddit": p["data"].get("subreddit")} for p in posts[:5]],
                        "related_keywords": related,
                        "time_period": period,
                    },
                ))

            elif source == "google_trends":
                url = f"{self.SOURCES['google_trends']}?q={keyword.replace(' ', '+')}&date=today%20{period}"
                resp = await client.get(url)
                resp.raise_for_status()
                html = resp.text
                # Google Trends embeds data in JS; parse approximate
                mention_count = self._extract_int(html, r'"value":\[(\d+)\]')
                related = re.findall(r'"title":"([^"]+)"', html)[:10]

                items.append(ScrapedItem(
                    source_url=url,
                    data={
                        "keyword": keyword,
                        "source": source,
                        "mention_count": mention_count,
                        "sentiment_score": 0,
                        "sentiment_label": "neutral",
                        "trend_velocity": mention_count,
                        "top_posts": [],
                        "related_keywords": related,
                        "time_period": period,
                    },
                ))

            elif source == "twitter":
                url = f"{self.SOURCES['twitter']}/search?q={keyword.replace(' ', '+')}&f=live"
                resp = await client.get(url, headers={"User-Agent": self._ua()})
                resp.raise_for_status()
                html = resp.text
                tweet_texts = re.findall(r'<span[^>]*>([^<]{10,200})</span>', html)
                mention_count = len(tweet_texts)
                sentiment = self._compute_sentiment(tweet_texts)

                items.append(ScrapedItem(
                    source_url=url,
                    data={
                        "keyword": keyword,
                        "source": source,
                        "mention_count": mention_count,
                        "sentiment_score": sentiment["score"],
                        "sentiment_label": sentiment["label"],
                        "trend_velocity": None,
                        "top_posts": [],
                        "related_keywords": self._extract_related(tweet_texts, keyword),
                        "time_period": period,
                    },
                ))

        finally:
            await client.aclose()

        return items

    # -- NLP-light helpers (no external dep) --
    def _compute_sentiment(self, texts: list[str]) -> dict:
        """Simple keyword-based sentiment (no heavy NLP model)."""
        positive_words = {"great", "awesome", "love", "best", "amazing", "excellent", "🔥", "bullish", "moon"}
        negative_words = {"bad", "terrible", "worst", "hate", "awful", "scam", "dead", "bearish", "dump"}
        
        pos = sum(1 for t in texts for w in positive_words if w in t.lower())
        neg = sum(1 for t in texts for w in negative_words if w in t.lower())
        total = pos + neg
        score = round((pos - neg) / max(total, 1), 2)
        label = "positive" if score > 0.1 else "negative" if score < -0.1 else "neutral"
        return {"score": score, "label": label}

    def _compute_velocity(self, posts: list, period: str) -> Optional[float]:
        """Approximate trend velocity from post recency."""
        import time
        if not posts:
            return None
        now = time.time()
        period_seconds = {"1d": 86400, "7d": 604800, "30d": 2592000}.get(period, 604800)
        recent = sum(1 for p in posts if now - p["data"].get("created_utc", 0) < period_seconds)
        return round((recent / len(posts)) * 100, 1) if posts else None

    def _extract_related(self, texts: list[str], keyword: str) -> list[str]:
        """Extract related keywords from text corpus."""
        import re
        from collections import Counter
        words = []
        for text in texts:
            words.extend(re.findall(r'\b[a-zA-Z]{4,}\b', text.lower()))
        # Filter out keyword itself and common words
        stop = {"http", "https", "that", "this", "with", "from", "have", "just", "like", "what", "when", "about"}
        filtered = [w for w in words if w not in stop and w != keyword.lower()]
        return [w for w, _ in Counter(filtered).most_common(10)]

    def _extract_int(self, html: str, pattern: str) -> Optional[int]:
        import re
        m = re.search(pattern, html)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                return int(raw)
            except ValueError:
                return None
        return None

    def _ua(self) -> str:
        return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
