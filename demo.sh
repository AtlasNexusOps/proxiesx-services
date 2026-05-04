#!/bin/bash
# Proxies.sx Demo Script — Amazon Tracker + Food Delivery
# Record with: asciinema rec --overwrite demo.cast --command "bash demo.sh"

clear
echo "╔══════════════════════════════════════════════════════╗"
echo "║  Proxies.sx Service Suite — Live Demo               ║"
echo "║  5 Bounties · $375 · x402 USDC Payments              ║"
echo "╚══════════════════════════════════════════════════════╝"
sleep 2

echo ""
echo "📁 Project Structure"
echo "─────────────────────"
tree -L 2 --dirsfirst -I '__pycache__|node_modules|.git' .
sleep 3

echo ""
echo "🔧 1. Shared Infrastructure"
echo "────────────────────────────"
echo ""
echo "Proxy Client (shared/proxy_client.py):"
echo "  → x402 payment flow (402 → pay USDC → proxy session)"
echo "  → Mobile User-Agent rotation"
echo "  → Session management"
echo ""
echo "Data Toolkit Pipeline (shared/scraper.py):"
echo "  → deduplicate() by content hash"
echo "  → filter_nulls() for clean output"
echo "  → to_json() / to_csv() export"
sleep 5

echo ""
echo "📦 2. Amazon Product & BSR Tracker (#72 — \$75)"
echo "────────────────────────────────────────────────"
echo ""
echo "Schema fields: asin, title, price_usd, bsr, rating, review_count, in_stock..."
echo ""
echo "Test run (simulated):"
python3 -c "
from amazon_tracker.tracker import AmazonTracker
import asyncio
tracker = AmazonTracker(country='US')
print('✅ AmazonTracker initialized')
print('   Schema:', list(tracker.schema()['properties'].keys())[:6], '...')
print('   Endpoints: /track/{ASIN} /category/{id} /search?q=...')
"
sleep 5

echo ""
echo "🍔 3. Food Delivery Price Intelligence (#76 — \$50)"
echo "─────────────────────────────────────────────────────"
echo ""
echo "Platforms: Uber Eats, Deliveroo, DoorDash"
echo "Schema: platform, restaurant_name, price, delivery_fee, rating..."
echo ""
python3 -c "
from food_delivery.tracker import FoodDeliveryTracker
tracker = FoodDeliveryTracker(country='US')
print('✅ FoodDeliveryTracker initialized')
print('   Platforms:', list(tracker.platforms.keys()))
print('   Endpoints: /compare?restaurant=X&zip=Y')
"
sleep 5

echo ""
echo "🔐 4. x402 Payment Gateway (gateway/index.mjs)"
echo "────────────────────────────────────────────────"
echo ""
echo "Tech: Node.js + Hono + @proxies-sx/x402-hono"
echo "Flow:  Request → x402 middleware → 402 Payment Required"
echo "       User pays USDC → Gateway retries → Python scraper"
echo "       Response ← Data Toolkit ← Scraper"
echo ""
echo "Pricing:"
echo "   /api/v1/track/{ASIN}         0.003 USDC"
echo "   /api/v1/compare?restaurant=X 0.002 USDC"
sleep 5

echo ""
echo "🐳 5. Deployment (Docker Compose)"
echo "───────────────────────────────────"
echo ""
grep -A2 "image\|container_name\|ports" docker-compose.yml | grep -v "^--$"
echo ""
echo "Deploy:  docker compose up -d"
echo "Verify:  curl http://localhost:3000/health"
sleep 4

echo ""
echo "╔══════════════════════════════════════════════════════╗"
echo "║  ✅ 2/5 services built — Ready for review            ║"
echo "║  Repo: github.com/AtlasNexusOps/proxiesx-services    ║"
echo "║  Claim: github.com/bolivian-peru/.../issues/421      ║"
echo "╚══════════════════════════════════════════════════════╝"
