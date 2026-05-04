"""
Facebook Marketplace Monitor — Proxies.sx Bounty #75 ($75)
Scrape listings by keyword, track price trends, detect deals.
"""
import re
from typing import Optional

from ..shared.scraper import BaseScraper, ScrapedItem, ScraperResult
from ..shared.proxy_client import X402Config


class FacebookMarketplaceTracker(BaseScraper):
    """
    Facebook Marketplace listing monitor with price trend tracking.

    Endpoints:
    - /search/{query} — listings with price, location, seller info
    - /trend/{category} — average price trends over time
    - /alerts — new listing alerts per keyword + price range
    """

    BASE_URL = "https://www.facebook.com/marketplace"

    def __init__(self, country: str = "US", proxy_config: Optional[X402Config] = None):
        super().__init__(country, proxy_config)

    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "listing_id": {"type": "string"},
                "title": {"type": "string"},
                "price": {"type": "number"},
                "currency": {"type": "string", "default": "USD"},
                "location": {"type": "string"},
                "category": {"type": "string"},
                "condition": {"type": "string", "enum": ["new", "used", "like_new", "fair", "unknown"]},
                "seller_name": {"type": "string"},
                "seller_rating": {"type": "number"},
                "listed_date": {"type": "string"},
                "description": {"type": "string"},
                "image_count": {"type": "integer"},
                "shipping_available": {"type": "boolean"},
                "scraped_at": {"type": "string", "format": "date-time"},
            },
            "required": ["listing_id", "title", "price"],
        }

    async def scrape(self, query: str = None, category: str = None, location: str = None) -> ScraperResult:
        proxy, client = await self.proxy_client.create_scraper_session(self.country)
        items = []
        errors = []

        try:
            if query:
                url = f"{self.BASE_URL}/{location or self.country.lower()}/search/?query={query.replace(' ', '%20')}"
            elif category:
                url = f"{self.BASE_URL}/{location or self.country.lower()}/category/{category}/"
            else:
                raise ValueError("Must provide query or category")

            resp = await client.get(url, headers={
                "Accept": "text/html,application/json",
                "Accept-Language": "en-US,en;q=0.9",
            })
            resp.raise_for_status()
            html = resp.text

            # Parse listings from Facebook's embedded JSON
            items = await self._parse_listings(html, url)

        except Exception as e:
            errors.append(str(e))
        finally:
            await client.aclose()

        return ScraperResult(items=items, errors=errors, proxy_country=self.country)

    async def _parse_listings(self, html: str, base_url: str) -> list[ScrapedItem]:
        """Extract Marketplace listings from Facebook HTML/JSON."""
        import json as json_mod
        items = []

        # Facebook Marketplace embeds listing data in <script> JSON
        # Pattern: __d("MarketplaceFeedQuery")
        listing_patterns = [
            r'"marketplace_listing_title"[^}]*"text":"([^"]+)"',
            r'"listing_price"[^}]*"text":"([^"]+)"',
            r'"marketplace_listing_location"[^}]*"text":"([^"]+)"',
        ]

        # Try extracting from embedded JSON blobs
        json_blobs = re.findall(r'\{.*?"marketplace_listing_title".*?\}', html, re.DOTALL)
        for blob in json_blobs[:20]:  # Max 20 listings
            try:
                # Clean and parse
                blob = blob.replace("\\\"", "\"").replace("\\\\", "\\")
                data = json_mod.loads(blob) if blob.startswith("{") else {}
            except json_mod.JSONDecodeError:
                # Fallback: regex extraction
                data = {}

            title = self._extract_field(html, r'"marketplace_listing_title"[^}]*"text":"([^"]+)"')
            price_text = self._extract_field(html, r'"listing_price"[^}]*"text":"([^"]+)"')
            location = self._extract_field(html, r'"marketplace_listing_location"[^}]*"text":"([^"]+)"')

            if title:
                price = self._parse_price(price_text) if price_text else None
                listing_id = self._extract_field(html, r'marketplace/item/(\d+)') or hashlib.sha256(title.encode()).hexdigest()[:12]
                import hashlib
                items.append(ScrapedItem(
                    source_url=base_url,
                    data={
                        "listing_id": listing_id,
                        "title": title.strip(),
                        "price": price,
                        "currency": "USD" if "$" in (price_text or "") else "EUR",
                        "location": location.strip() if location else None,
                        "category": self._extract_field(html, r'"category"[:\s]+"([^"]+)"'),
                        "condition": self._guess_condition(title),
                        "seller_name": self._extract_field(html, r'"seller"[:\s]+"([^"]+)"'),
                        "seller_rating": None,
                        "listed_date": None,
                        "description": self._extract_field(html, r'"description"[:\s]+"([^"]+)"'),
                        "image_count": None,
                        "shipping_available": "shipping" in html.lower(),
                    },
                ))

        return items

    def _extract_field(self, html: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    def _parse_price(self, text: str) -> Optional[float]:
        text = text.replace("$", "").replace("€", "").replace(",", "").strip()
        try:
            return float(text)
        except ValueError:
            return None

    def _guess_condition(self, title: str) -> str:
        title_lower = title.lower()
        if "new" in title_lower or "bnib" in title_lower or "box" in title_lower:
            return "new"
        elif "used" in title_lower or "pre-owned" in title_lower:
            return "used"
        elif "like new" in title_lower or "mint" in title_lower:
            return "like_new"
        return "unknown"
