/**
 * Proxies.sx x402 Gateway — Node.js + Hono + x402-hono middleware
 * 
 * Frontend: gates ALL requests behind USDC payment via x402 protocol
 * Backend: proxies to Python scraper services (Amazon, Food Delivery, etc.)
 * 
 * Architecture:
 *   User → x402 Gateway (USDC payment) → Python Scraper → Data Toolkit → Response
 */

import { Hono } from "hono";
import { x402 } from "@proxies-sx/x402-hono";

const app = new Hono();

// --- x402 Payment Middleware ---
// Every non-healthcheck request requires x402 payment
app.use("*", async (c, next) => {
  if (c.req.path === "/health" || c.req.path === "/") {
    return next();
  }
  return x402()(c, next);
});

// --- Backend proxy ---
const PYTHON_BACKEND = process.env.PYTHON_BACKEND || "http://scraper:8080";

async function proxyToPython(path, c) {
  const url = `${PYTHON_BACKEND}${path}${c.req.url.includes("?") ? "?" + new URL(c.req.url).searchParams.toString() : ""}`;
  try {
    const resp = await fetch(url, {
      method: c.req.method,
      headers: { "Accept": "application/json" },
    });
    const data = await resp.json();
    return c.json({
      ...data,
      x402_paid: true,
      gateway: "proxiesx-x402 v1.0.0",
    });
  } catch (e) {
    return c.json({ error: "Backend unreachable", detail: e.message }, 502);
  }
}

// --- Routes ---
app.get("/health", (c) => c.json({
  status: "ok",
  gateway: "x402-hono",
  version: "1.0.0",
  backend: PYTHON_BACKEND,
  services: ["amazon", "food-delivery"],
  pricing: {
    "amazon/track": "0.003 USDC",
    "amazon/category": "0.003 USDC",
    "food-delivery/compare": "0.002 USDC",
  },
}));

app.get("/api/v1/track/:asin", (c) => proxyToPython(`/api/v1/track/${c.req.param("asin")}`, c));
app.get("/api/v1/category/:id", (c) => proxyToPython(`/api/v1/category/${c.req.param("id")}`, c));
app.get("/api/v1/compare", (c) => proxyToPython("/api/v1/compare", c));
app.get("/api/v1/search", (c) => proxyToPython("/api/v1/search", c));

// 402 handler
app.onError((err, c) => {
  if (err.message?.includes("402") || err.status === 402) {
    return c.json({
      error: "Payment Required",
      message: "x402 USDC payment required — send USDC to continue",
      network: "solana",
      protocol: "x402",
    }, 402);
  }
  return c.json({ error: err.message }, 500);
});

// --- Start ---
const port = parseInt(process.env.PORT || "3000");
console.log(`🔐 x402 Gateway starting on port ${port}...`);
console.log(`   Backend: ${PYTHON_BACKEND}`);
console.log(`   Health:  http://localhost:${port}/health`);
console.log(`   Amazon:  http://localhost:${port}/api/v1/track/B08N5WRWNW`);
console.log(`   Food:    http://localhost:${port}/api/v1/compare?restaurant=McDonalds&zip=75001`);

export default {
  port,
  fetch: app.fetch,
};
