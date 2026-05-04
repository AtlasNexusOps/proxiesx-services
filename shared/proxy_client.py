"""
Proxies.sx Mobile Proxy Client
Handles x402 payment flow + proxy session acquisition.
"""
import asyncio
import hashlib
import time
from dataclasses import dataclass
from typing import Optional

import httpx


@dataclass
class ProxySession:
    """Acquired mobile proxy session."""
    proxy_url: str
    country: str
    session_id: str
    expires_at: float
    ip_address: Optional[str] = None


@dataclass
class X402Config:
    """x402 payment configuration."""
    base_url: str = "https://api.proxies.sx/v1/x402"
    usdc_wallet: Optional[str] = None  # Solana USDC wallet for payments
    max_cost_per_request: float = 0.01  # USDC cap per proxy session


class ProxiesSXClient:
    """
    Proxies.sx client with x402 payment flow.
    
    Flow:
    1. Request proxy → get 402 Payment Required + invoice
    2. Pay invoice in USDC → get proxy credentials
    3. Use proxy for scraping
    4. Proxy auto-expires after traffic cap
    """

    def __init__(self, config: X402Config = X402Config()):
        self.config = config
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
                follow_redirects=True,
            )
        return self._client

    async def acquire_proxy(
        self,
        country: str = "US",
        traffic_gb: float = 0.1,
    ) -> ProxySession:
        """
        Acquire a mobile proxy session via x402 payment flow.
        
        Args:
            country: 2-letter country code for proxy location
            traffic_gb: Traffic allowance in GB
            
        Returns:
            ProxySession with proxy_url and credentials
        """
        client = await self._get_client()
        session_id = _generate_session_id()

        # Step 1: Request proxy — expect 402 with invoice
        try:
            response = await client.get(
                f"{self.config.base_url}/proxy",
                params={
                    "country": country,
                    "traffic": traffic_gb,
                    "session": session_id,
                },
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 402:
                # Payment required — parse invoice
                invoice = e.response.json()
                await self._pay_invoice(invoice)
                # Retry after payment
                response = await client.get(
                    f"{self.config.base_url}/proxy",
                    params={
                        "country": country,
                        "traffic": traffic_gb,
                        "session": session_id,
                    },
                )
            else:
                raise

        response.raise_for_status()
        data = response.json()

        return ProxySession(
            proxy_url=data["proxy_url"],
            country=country,
            session_id=session_id,
            expires_at=time.time() + data.get("ttl_seconds", 300),
            ip_address=data.get("ip"),
        )

    async def _pay_invoice(self, invoice: dict) -> None:
        """
        Pay x402 invoice in USDC.
        In production: sign + send USDC transaction via Solana.
        For MVP: log invoice for manual payment or integrate x402-solana SDK.
        """
        # TODO: Integrate @proxies-sx/x402-solana for auto-payment
        invoice_id = invoice.get("id", "unknown")
        amount = invoice.get("amount_usdc", 0)
        print(f"💳 x402 Invoice #{invoice_id}: {amount} USDC — awaiting payment")
        # Placeholder: in production, this calls x402-solana SDK
        await asyncio.sleep(0)  # Non-blocking placeholder

    async def create_scraper_session(
        self, country: str = "US"
    ) -> tuple[ProxySession, httpx.AsyncClient]:
        """Acquire proxy + return an httpx client routed through it."""
        proxy = await self.acquire_proxy(country=country)
        transport = httpx.AsyncHTTPTransport(
            proxy=proxy.proxy_url,
            retries=3,
        )
        client = httpx.AsyncClient(
            transport=transport,
            timeout=httpx.Timeout(30.0),
            headers={
                "User-Agent": _random_mobile_ua(),
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        return proxy, client

    async def close(self):
        if self._client:
            await self._client.aclose()
            self._client = None


def _generate_session_id() -> str:
    return hashlib.sha256(f"{time.time()}{asyncio.get_event_loop()}".encode()).hexdigest()[:16]


def _random_mobile_ua() -> str:
    """Rotate realistic mobile User-Agents."""
    uas = [
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
        "Mozilla/5.0 (Linux; Android 14; Pixel 8 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.6261.119 Mobile Safari/537.36",
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_3 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/122.0.6261.89 Mobile/15E148 Safari/604.1",
    ]
    return uas[int(time.time()) % len(uas)]
