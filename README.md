Proxies.sx Service Suite

5-service Python scraping suite for the Proxies.sx marketplace — Amazon, Food Delivery, Trends, TikTok, Facebook Marketplace.
Built as a multi-bounty submission (Claim #421) with shared infrastructure across all services.

Services
ServiceFolderBountyStatusAmazon Product & BSR Trackeramazon-tracker/#72 — $75✅ LiveFood Delivery Price Intelligencefood-delivery/#76 — $50✅ LiveFacebook Marketplace Monitorfacebook-marketplace/#75🔄 In progressTrend Intelligencetrend-intelligence/#70🔄 In progressTikTok Trend Intelligencetiktok-trend/#51🔄 In progress

Architecture
proxiesx-services/
├── amazon-tracker/         ← Amazon product + BSR tracking
├── food-delivery/          ← Food delivery price intelligence
├── facebook-marketplace/   ← FB Marketplace monitor
├── trend-intelligence/     ← Web trend signals
├── tiktok-trend/           ← TikTok trend intelligence
│
├── shared/
│   ├── proxy_client.py     ← Proxies.sx x402 proxy acquisition
│   └── scraper.py          ← Base scraper + Data Toolkit pipeline
│
├── gateway/
├── server.py               ← x402 payment-gated API (all services)
├── Dockerfile
├── Dockerfile.gateway
├── docker-compose.yml
└── DEPLOY.md
All services share the same proxy client and base scraper. The gateway exposes a unified x402 payment-gated API endpoint.

Quickstart
Local
bashgit clone https://github.com/AtlasNexusOps/proxiesx-services.git
cd proxiesx-services

pip install -r requirements.txt

# 1. Configure shared settings
cp shared/config.yaml.example shared/config.yaml
# Edit config.yaml with your Proxies.sx credentials

# 2. Start the gateway API
python server.py --port 8080

# 3. Health check
curl http://localhost:8080/health
Docker
bashdocker-compose up -d

curl http://localhost:8080/health

Demo
bash# Run the interactive demo
bash demo.sh
The demo.cast file is an asciinema recording — play it with:
bashasciinema play demo.cast

Shared Infrastructure
shared/proxy_client.py
Handles Proxies.sx proxy acquisition via the x402 protocol. All scrapers import this module — proxy rotation is centralized and consistent across services.
shared/scraper.py
Base scraper class built on top of proxy_client.py. Integrates the Atlas Data Toolkit pipeline for cleaning and exporting scraped data to JSON/CSV.
server.py — Payment-gated API
Unified FastAPI gateway with x402 payment verification. All five services are accessible through a single endpoint with per-service routing.

Deployment
See DEPLOY.md for production deployment instructions including environment variables, Docker configuration, and proxy setup.

Atlas Nexus Context
This repository is part of the Atlas Nexus data operations suite:

marketplace intelligence for e-commerce and trend monitoring
proxy-native scraping infrastructure for high-availability data collection
payment-gated API layer compatible with automated agent workflows

Main site: atlasnexusops.github.io

License
MIT — Atlas Nexus, 2026
