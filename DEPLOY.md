# Proxies.sx Service Suite — Deployment Guide

## 🏗️ Architecture

```
Internet → Gateway (x402 USDC) → Python Scraper → Data Toolkit → JSON/CSV
              ↑ Node.js              ↑ Python 3.12
          @proxies-sx/x402-hono    Playwright + httpx
```

## 🚀 Quick Deploy (VPS)

### Prerequisites
- Ubuntu 22.04+ / Debian 12+
- Docker + Docker Compose
- 2 GB RAM, 10 GB disk
- Solana wallet with USDC (for proxy payments)

### 1. Clone & Configure

```bash
git clone https://github.com/AtlasNexusOps/proxiesx-services.git
cd proxiesx-services

# Edit shared/config.yaml with your preferences
nano shared/config.yaml
```

### 2. Set Environment

```bash
# .env file
echo 'PROXIES_COUNTRY=US' > .env
echo 'GATEWAY_PORT=3000' >> .env
```

### 3. Build & Start

```bash
docker compose build
docker compose up -d

# Verify
curl http://localhost:3000/health
```

### 4. Test an Endpoint

```bash
# Amazon product track (returns 402 Payment Required → pay USDC → get data)
curl http://localhost:3000/api/v1/track/B08N5WRWNW

# Food delivery compare (returns 402 → pay → get data)
curl "http://localhost:3000/api/v1/compare?restaurant=McDonalds&zip=75001"
```

## 📊 Service Endpoints

| Service | Endpoint | Price | Bounty |
|---------|----------|-------|--------|
| Amazon Tracker | `/api/v1/track/{ASIN}` | 0.003 USDC | #72 $75 |
| Amazon Category | `/api/v1/category/{id}` | 0.003 USDC | #72 $75 |
| Food Delivery | `/api/v1/compare?restaurant=X&zip=Y` | 0.002 USDC | #76 $50 |
| Healthcheck | `/health` | Free | — |

## 🔧 Monitoring

```bash
# Logs
docker compose logs -f scraper
docker compose logs -f gateway

# Stats
docker stats proxiesx-scraper proxiesx-gateway

# Restart
docker compose restart
```

## 🔒 Security Notes

- Python scraper is NOT exposed to internet — only accessible via internal Docker network
- All external requests MUST pay USDC via x402 before reaching scrapers
- Rate limiting: 60 req/min by default (configurable in `shared/config.yaml`)
- Proxy IPs rotate per session via Proxies.sx mobile proxy pool

## 💰 Revenue Model

| Tier | Revenue | How |
|------|---------|-----|
| Bounty | $375 one-time | 5 bounties × $50–100 in $SX |
| Marketplace | $0.002–0.003/query | Ongoing USDC per API call |
| Margin | ~75–80% | After proxy costs (~$0.0005/query) |
