# Proxies.sx Service Suite — Multi-Bounty Claim #421
#
# 5 services, 1 shared infrastructure:
#   amazon-tracker/     — #72  Amazon Product & BSR Tracker ($75)
#   food-delivery/      — #76  Food Delivery Price Intelligence ($50)
#   (facebook-marketplace/  — #75  Facebook Marketplace Monitor — coming)
#   (trend-intelligence/    — #70  Trend Intelligence — coming)
#   (tiktok-trend/          — #51  TikTok Trend Intelligence — coming)
#
# Shared:
#   shared/proxy_client.py  — Proxies.sx x402 proxy acquisition
#   shared/scraper.py       — Base scraper + Data Toolkit pipeline
#
# Gateway:
#   server.py               — x402 payment-gated API (all services)
#
# Quickstart:
#   1. Configure shared/config.yaml
#   2. python server.py --port 8080
#   3. curl http://localhost:8080/health
