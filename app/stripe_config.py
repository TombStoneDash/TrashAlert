"""Stripe configuration for TrashAlert subscription billing.

Environment variables required:
  STRIPE_SECRET_KEY       — sk_live_... or sk_test_...
  STRIPE_WEBHOOK_SECRET   — whsec_...
  STRIPE_PUBLISHABLE_KEY  — pk_live_... or pk_test_...

Create products + prices in Stripe Dashboard first, then set the
price IDs below (or override via env vars).
"""

import os

STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")

# Base URL for success/cancel redirects
BASE_URL = os.getenv("BASE_URL", "https://trashalert.io")

# Stripe Price IDs — set these after creating products in the Stripe Dashboard.
# Override via env vars for different environments (test vs live).
PRICE_STARTER = os.getenv("STRIPE_PRICE_STARTER", "price_starter_placeholder")
PRICE_PORTFOLIO = os.getenv("STRIPE_PRICE_PORTFOLIO", "price_portfolio_placeholder")

# Plan metadata for display and logic
PLANS = {
    "starter": {
        "name": "Starter",
        "price_id": PRICE_STARTER,
        "amount": 2900,       # $29.00 in cents
        "currency": "usd",
        "interval": "month",
        "properties": 1,
        "features": [
            "1 property",
            "Schedule lookup",
            "Weekly email reminders",
            "Zone map access",
            "Basic API (100 req/day)",
        ],
    },
    "portfolio": {
        "name": "Portfolio",
        "price_id": PRICE_PORTFOLIO,
        "amount": 9900,       # $99.00 in cents
        "currency": "usd",
        "interval": "month",
        "properties": -1,     # unlimited
        "features": [
            "Unlimited properties",
            "Bulk CSV upload",
            "Embeddable tenant widget",
            "REST API (10k req/day)",
            "Bulk schedule endpoint",
            "Branded move-in packets",
            "Slack & email alerts",
        ],
    },
}
