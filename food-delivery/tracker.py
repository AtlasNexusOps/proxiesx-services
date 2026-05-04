"""
Food Delivery Price Intelligence — Proxies.sx Bounty #76 ($50)
Cross-platform price comparison: Uber Eats / Deliveroo / DoorDash.
"""
import asyncio
from typing import Optional

from ..shared.scraper import BaseScraper, ScrapedItem, ScraperResult
from ..shared.proxy_client import X402Config


class FoodDeliveryTracker(BaseScraper):
    """
    Multi-platform food delivery price tracker.

    Endpoints:
    - /compare — same meal across platforms
    - /restaurant/{id} — menu + price history
    - /zone/{zip} — cheapest delivery zone scan
    """

    PLATFORMS = {
        "ubereats": "https://www.ubereats.com",
        "deliveroo": "https://deliveroo.fr",
        "doordash": "https://www.doordash.com",
    }

    def __init__(self, country: str = "US", proxy_config: Optional[X402Config] = None):
        super().__init__(country, proxy_config)
        self.platforms = self.PLATFORMS.copy()
        if country.upper() == "FR":
            self.platforms["deliveroo"] = "https://deliveroo.fr"
            self.platforms["ubereats"] = "https://www.ubereats.com/fr"

    def schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "platform": {"type": "string", "enum": list(self.PLATFORMS.keys())},
                "restaurant_name": {"type": "string"},
                "restaurant_id": {"type": "string"},
                "item_name": {"type": "string"},
                "price": {"type": "number", "minimum": 0},
                "currency": {"type": "string", "default": "USD"},
                "delivery_fee": {"type": "number"},
                "service_fee": {"type": "number"},
                "total_price": {"type": "number"},
                "estimated_delivery_min": {"type": "integer"},
                "rating": {"type": "number", "minimum": 0, "maximum": 5},
                "rating_count": {"type": "integer"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "available": {"type": "boolean"},
                "scraped_at": {"type": "string", "format": "date-time"},
            },
            "required": ["platform", "restaurant_name", "price"],
        }

    async def scrape(
        self,
        restaurant: str = None,
        zip_code: str = None,
        meal: str = None,
        platforms: list[str] = None,
    ) -> ScraperResult:
        """
        Compare food delivery prices across platforms.

        Args:
            restaurant: Restaurant name to search
            zip_code: Delivery zone
            meal: Specific meal/item to compare
            platforms: List of platforms to check (default: all)
        """
        platforms = platforms or list(self.platforms.keys())
        items = []
        errors = []

        for platform_name in platforms:
            try:
                platform_items = await self._scrape_platform(
                    platform_name, restaurant, zip_code, meal
                )
                items.extend(platform_items)
            except Exception as e:
                errors.append(f"{platform_name}: {e}")

        return ScraperResult(items=items, errors=errors, proxy_country=self.country)

    async def _scrape_platform(
        self, platform: str, restaurant: str = None, zip_code: str = None, meal: str = None
    ) -> list[ScrapedItem]:
        """Scrape a single delivery platform."""
        proxy, client = await self.proxy_client.create_scraper_session(self.country)
        items = []

        try:
            base = self.platforms.get(platform)
            if not base:
                raise ValueError(f"Unknown platform: {platform}")

            # Build search URL per platform
            if restaurant:
                if platform == "ubereats":
                    url = f"{base}/search?q={restaurant.replace(' ', '+')}"
                    if zip_code:
                        url += f"&postalCode={zip_code}"
                elif platform == "deliveroo":
                    url = f"{base}/restaurants/?q={restaurant.replace(' ', '+')}"
                elif platform == "doordash":
                    url = f"{base}/search/{restaurant.replace(' ', '-')}/"
                else:
                    url = f"{base}/search?q={restaurant.replace(' ', '+')}"
            elif zip_code:
                url = f"{base}/home?postalCode={zip_code}"
            else:
                raise ValueError("Must provide restaurant or zip_code")

            resp = await client.get(url)
            resp.raise_for_status()
            html = resp.text

            # Parse restaurant listings from HTML
            extracted = await self._parse_listings(html, platform, base)
            items.extend(extracted)

        finally:
            await client.aclose()

        return items

    async def _parse_listings(self, html: str, platform: str, base_url: str) -> list[ScrapedItem]:
        """Extract restaurant/menu data from platform HTML."""
        import re
        import json as json_mod
        items = []

        # Try JSON-LD embedded data first (most delivery platforms use it)
        ld_pattern = r'<script type="application/ld\+json"[^>]*>(.*?)</script>'
        for match in re.finditer(ld_pattern, html, re.DOTALL):
            try:
                ld_data = json_mod.loads(match.group(1))
                if isinstance(ld_data, dict) and ld_data.get("@type") in ("Restaurant", "MenuItem", "Menu"):
                    items.append(ScrapedItem(
                        source_url=f"{base_url}",
                        data={
                            "platform": platform,
                            "restaurant_name": ld_data.get("name", "Unknown"),
                            "restaurant_id": ld_data.get("@id", ""),
                            "item_name": ld_data.get("name", ""),
                            "price": float(ld_data.get("offers", {}).get("price", 0)) if ld_data.get("offers") else None,
                            "currency": ld_data.get("offers", {}).get("priceCurrency", "USD") if ld_data.get("offers") else "USD",
                            "delivery_fee": None,
                            "service_fee": None,
                            "total_price": float(ld_data.get("offers", {}).get("price", 0)) if ld_data.get("offers") else None,
                            "estimated_delivery_min": None,
                            "rating": float(ld_data.get("aggregateRating", {}).get("ratingValue", 0)) if ld_data.get("aggregateRating") else None,
                            "rating_count": int(ld_data.get("aggregateRating", {}).get("reviewCount", 0)) if ld_data.get("aggregateRating") else None,
                            "tags": ld_data.get("servesCuisine", "").split(",") if ld_data.get("servesCuisine") else [],
                            "available": True,
                        },
                    ))
            except (json_mod.JSONDecodeError, KeyError, ValueError):
                continue

        return items
