"""
TikTok Trend Intelligence — Proxies.sx Bounty #51 ($75)
Track hashtags, creators, and trending content via mobile proxies.
"""
import re
from typing import Optional

from ..shared.scraper import BaseScraper, ScrapedItem, ScraperResult
from ..shared.proxy_client import X402Config


class TikTokTrendTracker(BaseScraper):
    """
    TikTok trend intelligence with hashtag & creator analytics.

    Endpoints:
    - /hashtag/{tag} — views, posts, growth rate
    - /creator/{username} — engagement rate, follower velocity
    - /trending — current trending sounds + hashtags
    """

    BASE_URL = "https://www.tiktok.com"

    def __init__(self, country: str = "US", proxy_config: Optional[X402Config] = None):
        super().__init__(country, proxy_config)

    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "default": "tiktok"},
                "hashtag": {"type": "string"},
                "total_views": {"type": "integer"},
                "total_posts": {"type": "integer"},
                "growth_rate_7d": {"type": "number", "description": "Growth % over 7 days"},
                "top_videos": {"type": "array", "items": {"type": "object"}},
                "trending_regions": {"type": "array", "items": {"type": "string"}},
                "creator_username": {"type": "string"},
                "follower_count": {"type": "integer"},
                "engagement_rate": {"type": "number"},
                "avg_views_per_post": {"type": "integer"},
                "follower_velocity_30d": {"type": "number"},
                "scraped_at": {"type": "string", "format": "date-time"},
            },
        }

    async def scrape(self, hashtag: str = None, creator: str = None, trending: bool = False) -> ScraperResult:
        proxy, client = await self.proxy_client.create_scraper_session(self.country)
        items = []
        errors = []

        try:
            if hashtag:
                item = await self._scrape_hashtag(client, hashtag)
                if item:
                    items.append(item)

            elif creator:
                item = await self._scrape_creator(client, creator)
                if item:
                    items.append(item)

            elif trending:
                trending_items = await self._scrape_trending(client)
                items.extend(trending_items)

        except Exception as e:
            errors.append(str(e))
        finally:
            await client.aclose()

        return ScraperResult(items=items, errors=errors, proxy_country=self.country)

    async def _scrape_hashtag(self, client, tag: str) -> Optional[ScrapedItem]:
        """Scrape hashtag analytics."""
        url = f"{self.BASE_URL}/tag/{tag.lstrip('#')}"
        resp = await client.get(url, headers={"User-Agent": self._mobile_ua()})
        resp.raise_for_status()
        html = resp.text

        views = self._extract_int(html, r'"videoCount":(\d+)') or self._extract_int(html, r'(\d[\d,.]*[KMB]?)\s*views')
        posts = self._extract_int(html, r'"postCount":(\d+)')

        return ScrapedItem(
            source_url=url,
            data={
                "platform": "tiktok",
                "hashtag": f"#{tag.lstrip('#')}",
                "total_views": views,
                "total_posts": posts,
                "growth_rate_7d": self._parse_growth(html),
                "top_videos": self._parse_top_videos(html),
                "trending_regions": self._parse_regions(html),
                "creator_username": None,
                "follower_count": None,
                "engagement_rate": None,
                "avg_views_per_post": None,
                "follower_velocity_30d": None,
            },
        )

    async def _scrape_creator(self, client, username: str) -> Optional[ScrapedItem]:
        """Scrape creator profile analytics."""
        url = f"{self.BASE_URL}/@{username.lstrip('@')}"
        resp = await client.get(url, headers={"User-Agent": self._mobile_ua()})
        resp.raise_for_status()
        html = resp.text

        followers = self._extract_int(html, r'"followerCount":(\d+)') or \
                    self._extract_int(html, r'(\d[\d,.]*[KMB]?)\s*Followers')
        likes = self._extract_int(html, r'"heartCount":(\d+)') or \
                self._extract_int(html, r'(\d[\d,.]*[KMB]?)\s*Likes')
        following = self._extract_int(html, r'"followingCount":(\d+)')
        video_count = self._extract_int(html, r'"videoCount":(\d+)')

        engagement = None
        if followers and likes and followers > 0:
            engagement = round((likes / followers) * 100, 2) if video_count else None

        avg_views = None
        if video_count and video_count > 0:
            avg_views_raw = self._extract_int(html, r'"playCount":(\d+)')
            if avg_views_raw:
                avg_views = avg_views_raw // video_count

        return ScrapedItem(
            source_url=url,
            data={
                "platform": "tiktok",
                "hashtag": None,
                "total_views": None,
                "total_posts": None,
                "growth_rate_7d": None,
                "top_videos": [],
                "trending_regions": [],
                "creator_username": f"@{username.lstrip('@')}",
                "follower_count": followers,
                "engagement_rate": engagement,
                "avg_views_per_post": avg_views,
                "follower_velocity_30d": self._parse_velocity(html),
            },
        )

    async def _scrape_trending(self, client) -> list[ScrapedItem]:
        """Scrape trending hashtags and sounds."""
        url = f"{self.BASE_URL}/trending"
        resp = await client.get(url, headers={"User-Agent": self._mobile_ua()})
        resp.raise_for_status()
        html = resp.text

        items = []
        # Extract trending hashtags
        tags = re.findall(r'"title":"([^"]+)"', html)
        for tag in tags[:20]:
            if not tag.startswith("#"):
                tag = f"#{tag}"
            items.append(ScrapedItem(
                source_url=url,
                data={
                    "platform": "tiktok",
                    "hashtag": tag,
                    "total_views": None,
                    "total_posts": None,
                    "growth_rate_7d": None,
                    "top_videos": [],
                    "trending_regions": ["global"],
                    "creator_username": None,
                    "follower_count": None,
                    "engagement_rate": None,
                    "avg_views_per_post": None,
                    "follower_velocity_30d": None,
                },
            ))
        return items

    # -- Helpers --
    def _extract_int(self, html: str, pattern: str) -> Optional[int]:
        m = re.search(pattern, html, re.IGNORECASE)
        if not m:
            return None
        raw = m.group(1).replace(",", "").replace(".", "")
        multipliers = {"K": 1000, "M": 1000000, "B": 1000000000}
        for suffix, mult in multipliers.items():
            if suffix in raw:
                raw = raw.replace(suffix, "")
                return int(float(raw) * mult)
        try:
            return int(raw)
        except ValueError:
            return None

    def _parse_growth(self, html: str) -> Optional[float]:
        m = re.search(r'(\d+\.?\d*)%\s*(?:growth|increase)', html, re.IGNORECASE)
        return float(m.group(1)) if m else None

    def _parse_top_videos(self, html: str) -> list[dict]:
        videos = []
        ids = re.findall(r'"video_id":"(\d+)"', html)
        for vid in ids[:5]:
            videos.append({"video_id": vid, "url": f"https://www.tiktok.com/@/video/{vid}"})
        return videos

    def _parse_regions(self, html: str) -> list[str]:
        regions = re.findall(r'"region":"([A-Z]{2})"', html)
        return list(set(regions))[:5] if regions else ["global"]

    def _parse_velocity(self, html: str) -> Optional[float]:
        m = re.search(r'(\d+\.?\d*)%\s*(?:growth|velocity|increase)', html, re.IGNORECASE)
        return float(m.group(1)) if m else None

    def _mobile_ua(self) -> str:
        return "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1"
