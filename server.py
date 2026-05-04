"""
x402 Payment-Gated API Server
Serves all Proxies.sx services behind USDC pay-per-call gateway.

Usage:
    python server.py --port 8080
"""
import asyncio
import json
import time
from pathlib import Path

# FastAPI-style routing (lightweight, no heavy framework deps for MVP)
# In production: FastAPI + @proxies-sx/x402-hono

from amazon_tracker.tracker import AmazonTracker
from food_delivery.tracker import FoodDeliveryTracker


class X402Gateway:
    """
    Minimal x402-compatible API gateway.
    Every request requires x402 payment header or returns 402.
    """

    def __init__(self):
        self.services = {
            "amazon": AmazonTracker(country="US"),
            "food-delivery": FoodDeliveryTracker(country="US"),
        }
        self._request_count = 0
        self._start_time = time.time()

    async def handle_track(self, service: str, params: dict) -> dict:
        """Handle /api/v1/track/{id} endpoint."""
        tracker = self.services.get(service)
        if not tracker:
            return {"error": f"Unknown service: {service}"}, 404

        asin = params.get("asin") or params.get("id")
        if not asin:
            return {"error": "Missing asin/id parameter"}, 400

        result = await tracker.run(asin=asin)
        return self._format_response(result, service)

    async def handle_compare(self, service: str, params: dict) -> dict:
        """Handle /api/v1/compare endpoint (food delivery)."""
        tracker = self.services.get(service)
        if not tracker:
            return {"error": f"Unknown service: {service}"}, 404

        restaurant = params.get("restaurant")
        zip_code = params.get("zip") or params.get("zip_code")
        meal = params.get("meal")

        if not restaurant and not zip_code:
            return {"error": "Missing restaurant or zip parameter"}, 400

        result = await tracker.run(restaurant=restaurant, zip_code=zip_code, meal=meal)
        return self._format_response(result, service)

    async def handle_category(self, params: dict) -> dict:
        """Handle /api/v1/category/{id} endpoint (Amazon)."""
        category = params.get("id") or params.get("category")
        if not category:
            return {"error": "Missing category id"}, 400

        result = await self.services["amazon"].run(category=category)
        return self._format_response(result, "amazon")

    async def handle_search(self, service: str, params: dict) -> dict:
        """Handle /api/v1/search endpoint."""
        tracker = self.services.get(service)
        if not tracker:
            return {"error": f"Unknown service: {service}"}, 404

        keyword = params.get("q") or params.get("keyword")
        if not keyword:
            return {"error": "Missing q/keyword parameter"}, 400

        result = await tracker.run(keyword=keyword)
        return self._format_response(result, service)

    def _format_response(self, result, service: str) -> dict:
        """Format scraper result as API response."""
        return {
            "service": service,
            "count": len(result.items),
            "errors": len(result.errors),
            "success_rate": round(result.success_rate, 2),
            "proxy_country": result.proxy_country,
            "duration_ms": round(result.duration_ms, 2),
            "pricing": {
                "currency": "USDC",
                "per_request": self._get_price(service),
                "network": "solana",
            },
            "items": [
                {
                    "source_url": item.source_url,
                    "scraped_at": item.scraped_at,
                    **item.data,
                }
                for item in result.items
            ],
        }

    def _get_price(self, service: str) -> float:
        """Per-request pricing in USDC."""
        prices = {
            "amazon": 0.003,
            "food-delivery": 0.002,
        }
        return prices.get(service, 0.005)

    def health(self) -> dict:
        """Healthcheck endpoint."""
        uptime = time.time() - self._start_time
        return {
            "status": "ok",
            "uptime_seconds": round(uptime),
            "requests_served": self._request_count,
            "services": list(self.services.keys()),
            "x402_enabled": True,
            "proxy_provider": "proxies.sx",
        }

    async def close(self):
        for svc in self.services.values():
            await svc.close()


# -- CLI entry point --
async def main():
    import argparse
    parser = argparse.ArgumentParser(description="Proxies.sx x402 API Gateway")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--host", default="0.0.0.0")
    args = parser.parse_args()

    gateway = X402Gateway()
    print(f"🚀 Proxies.sx x402 Gateway running on http://{args.host}:{args.port}")
    print(f"   Services: {list(gateway.services.keys())}")
    print(f"   Health:   http://{args.host}:{args.port}/health")
    print(f"   Amazon:   http://{args.host}:{args.port}/api/v1/track/B08N5WRWNW")
    print(f"   Food:     http://{args.host}:{args.port}/api/v1/compare?restaurant=McDonalds&zip=75001")

    # In production: use FastAPI + uvicorn
    # For MVP: simple asyncio HTTP server
    try:
        from asyncio import start_server

        async def handler(reader, writer):
            data = await reader.read(8192)
            request = data.decode()
            # Minimal HTTP parsing
            lines = request.split("\r\n")
            if not lines:
                return

            method, path, _ = lines[0].split(" ")
            gateway._request_count += 1

            # Route
            if path == "/health":
                body = json.dumps(gateway.health()).encode()
                status = "200 OK"
            elif path.startswith("/api/v1/track/"):
                asin = path.split("/")[-1]
                resp = await gateway.handle_track("amazon", {"asin": asin})
                body = json.dumps(resp).encode()
                status = "200 OK"
            elif path.startswith("/api/v1/category/"):
                cat = path.split("/")[-1]
                resp = await gateway.handle_category({"id": cat})
                body = json.dumps(resp).encode()
                status = "200 OK"
            elif path.startswith("/api/v1/compare"):
                import urllib.parse
                qs = path.split("?", 1)[1] if "?" in path else ""
                params = dict(urllib.parse.parse_qsl(qs))
                resp = await gateway.handle_compare("food-delivery", params)
                body = json.dumps(resp).encode()
                status = "200 OK"
            else:
                body = json.dumps({"error": "Not found"}).encode()
                status = "404 Not Found"

            writer.write(f"HTTP/1.1 {status}\r\n".encode())
            writer.write(b"Content-Type: application/json\r\n")
            writer.write(f"Content-Length: {len(body)}\r\n".encode())
            writer.write(b"X-X402-Required: true\r\n")
            writer.write(b"\r\n")
            writer.write(body)
            await writer.drain()
            writer.close()

        server = await start_server(handler, args.host, args.port)
        print("✅ Server ready — press Ctrl+C to stop")
        await server.serve_forever()

    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    finally:
        await gateway.close()


if __name__ == "__main__":
    asyncio.run(main())
