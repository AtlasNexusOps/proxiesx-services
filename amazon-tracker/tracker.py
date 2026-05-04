"""
Amazon Product & BSR Tracker — Proxies.sx Bounty #72 ($75)
Tracks product price, BSR, stock, ratings via mobile proxies.
"""
import asyncio
import re
from typing import Optional

from ..shared.scraper import BaseScraper, ScrapedItem, ScraperResult
from ..shared.proxy_client import X402Config


class AmazonTracker(BaseScraper):
    """
    Amazon product tracker with BSR (Best Sellers Rank) monitoring.

    Endpoints:
    - /track/{asin} — price, BSR, stock, rating, review count
    - /category/{category} — top 100 with BSR trend
    - /alerts — configurable price drop alerts
    """

    BASE_URL = "https://www.amazon.com"
    # ASIN pattern: 10 alphanumeric chars starting with B
    ASIN_RE = re.compile(r"/dp/(B[A-Z0-9]{9})")

    def __init__(self, country: str = "US", proxy_config: Optional[X402Config] = None):
        super().__init__(country, proxy_config)

    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "asin": {"type": "string", "pattern": "^B[A-Z0-9]{9}$"},
                "title": {"type": "string"},
                "price_usd": {"type": "number", "minimum": 0},
                "list_price_usd": {"type": "number"},
                "currency": {"type": "string", "default": "USD"},
                "bsr": {"type": "integer", "description": "Best Sellers Rank"},
                "bsr_category": {"type": "string"},
                "rating": {"type": "number", "minimum": 0, "maximum": 5},
                "review_count": {"type": "integer", "minimum": 0},
                "in_stock": {"type": "boolean"},
                "seller": {"type": "string"},
                "prime_eligible": {"type": "boolean"},
                "coupon_text": {"type": "string"},
                "variations": {"type": "array", "items": {"type": "object"}},
                "scraped_at": {"type": "string", "format": "date-time"},
            },
            "required": ["asin", "title", "price_usd"],
        }

    async def scrape(self, asin: str = None, category: str = None, keyword: str = None) -> ScraperResult:
        """
        Scrape Amazon product data.

        Args:
            asin: Single ASIN to track (e.g., B08N5WRWNW)
            category: Category node ID for top-100 scraping
            keyword: Search keyword for product discovery
        """
        proxy, client = await self.proxy_client.create_scraper_session(self.country)
        items = []
        errors = []

        try:
            if asin:
                product = await self._scrape_product(client, asin)
                if product:
                    items.append(product)
                else:
                    errors.append(f"Failed to scrape ASIN {asin}")

            elif category:
                top_asins = await self._scrape_category_top(client, category)
                # Scrape first 10 in parallel
                tasks = [self._scrape_product(client, a) for a in top_asins[:10]]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        errors.append(str(r))
                    elif r:
                        items.append(r)

            elif keyword:
                search_asins = await self._search_products(client, keyword)
                tasks = [self._scrape_product(client, a) for a in search_asins[:5]]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for r in results:
                    if isinstance(r, Exception):
                        errors.append(str(r))
                    elif r:
                        items.append(r)

        finally:
            await client.aclose()

        return ScraperResult(items=items, errors=errors, proxy_country=self.country)

    async def _scrape_product(self, client, asin: str) -> Optional[ScrapedItem]:
        """Scrape a single product page."""
        url = f"{self.BASE_URL}/dp/{asin}"
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text
        except Exception as e:
            raise ValueError(f"HTTP error for {asin}: {e}")

        # Extract product data from HTML
        title = self._extract(html, r'"title":"([^"]+)"') or self._extract(html, r'<span id="productTitle"[^>]*>([^<]+)')

        price = self._extract_price(html, r'"price":(\d+\.?\d*)') or \
                self._extract_price(html, r'<span class="a-price[^"]*"[^>]*>.*?<span[^>]*>([\d.,]+)') or \
                self._parse_price_span(html)

        list_price = self._extract_price(html, r'"listPrice":(\d+\.?\d*)') or \
                     self._extract_price(html, r'<span class="a-text-price"[^>]*>.*?([\d.,]+)')

        bsr = self._extract_int(html, r'"salesRank":(\d+)')
        bsr_cat = self._extract(html, r'"salesRankShortName":"([^"]+)"')

        rating = self._extract_float(html, r'"ratingValue":"([\d.]+)"') or \
                 self._extract_float(html, r'average customer rating[:\s]*([\d.]+)')

        reviews = self._extract_int(html, r'"reviewCount":"(\d+)"') or \
                  self._extract_int(html, r'([\d,]+) (?:global )?ratings?')

        stock = "Currently unavailable" not in html
        seller = self._extract(html, r'Sold by[:\s]*<[^>]*>([^<]+)')
        prime = "prime" in html.lower() and "not-prime" not in html.lower()
        coupon = self._extract(html, r'couponBadgeText["\s:]+([^"]+)') or \
                 self._extract(html, r'Save\s+\d+%')

        if not title:
            raise ValueError(f"Could not extract product data for {asin}")

        return ScrapedItem(
            source_url=url,
            data={
                "asin": asin,
                "title": title.strip(),
                "price_usd": price,
                "list_price_usd": list_price,
                "currency": "USD",
                "bsr": bsr,
                "bsr_category": bsr_cat,
                "rating": rating,
                "review_count": reviews,
                "in_stock": stock,
                "seller": seller,
                "prime_eligible": prime,
                "coupon_text": coupon,
            },
        )

    async def _scrape_category_top(self, client, category_id: str) -> list[str]:
        """Get top-selling ASINs in a category."""
        url = f"{self.BASE_URL}/gp/bestsellers/{category_id}"
        resp = await client.get(url)
        resp.raise_for_status()
        return self.ASIN_RE.findall(resp.text)[:10]

    async def _search_products(self, client, keyword: str) -> list[str]:
        """Search products and return ASINs."""
        url = f"{self.BASE_URL}/s?k={keyword.replace(' ', '+')}"
        resp = await client.get(url)
        resp.raise_for_status()
        return self.ASIN_RE.findall(resp.text)[:5]

    # -- HTML extraction helpers --
    def _extract(self, html: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
        return m.group(1).strip() if m else None

    def _extract_price(self, html: str, pattern: str) -> Optional[float]:
        raw = self._extract(html, pattern)
        if raw:
            raw = raw.replace(",", "").replace("$", "").replace("€", "").strip()
            try:
                return float(raw)
            except ValueError:
                return None
        return None

    def _extract_int(self, html: str, pattern: str) -> Optional[int]:
        raw = self._extract(html, pattern)
        if raw:
            raw = raw.replace(",", "")
            try:
                return int(raw)
            except ValueError:
                return None
        return None

    def _extract_float(self, html: str, pattern: str) -> Optional[float]:
        raw = self._extract(html, pattern)
        if raw:
            try:
                return float(raw)
            except ValueError:
                return None
        return None

    def _parse_price_span(self, html: str) -> Optional[float]:
        """Fallback: parse a-price-whole + a-price-fraction."""
        whole = self._extract(html, r'<span class="a-price-whole">([^<]+)')
        fraction = self._extract(html, r'<span class="a-price-fraction">(\d+)')
        if whole:
            whole = whole.replace(",", "").strip()
            price = float(whole)
            if fraction:
                price += float(fraction) / 100
            return price
        return None
