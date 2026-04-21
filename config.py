"""
config.py — load and validate proxy configuration from environment.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _list(key: str, default: str = "") -> list[str]:
    raw = os.getenv(key, default)
    return [v.strip() for v in raw.split(",") if v.strip()]


# ── Network ───────────────────────────────────────────────────────────────────
PORT: int = int(os.getenv("PORT", "8080"))

# IPs allowed to use the proxy (comma-separated in .env)
ALLOWED_IPS: list[str] = _list("ALLOWED_IPS", "127.0.0.1")

# ── Models ────────────────────────────────────────────────────────────────────
ALLOWED_MODELS: list[str] = _list(
    "ALLOWED_MODELS",
    "claude-sonnet-4-6,"
    "claude-sonnet-4-20250514,"
    "claude-haiku-4-5-20251001,"
    "claude-sonnet-4-5",
)

# ── Limits ────────────────────────────────────────────────────────────────────
DAILY_LIMIT_USD: float = float(os.getenv("DAILY_LIMIT", "10.0"))

# ── Pseudo-keys → project names ───────────────────────────────────────────────
# Format in .env:  PSEUDO_KEY_GOLF=sk-proxy-golf-xxxxxxxx
# Any env var starting with PSEUDO_KEY_ is loaded automatically.
PSEUDO_KEYS: dict[str, str] = {}
for k, v in os.environ.items():
    if k.startswith("PSEUDO_KEY_") and v.strip():
        project = k[len("PSEUDO_KEY_"):].lower()
        PSEUDO_KEYS[v.strip()] = project

# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_URL = "https://api.anthropic.com"

# ── Model pricing (USD per 1M tokens) ────────────────────────────────────────
# Update as Anthropic changes pricing.
MODEL_PRICING: dict[str, dict] = {
    "claude-sonnet-4-6":           {"in": 3.0,  "out": 15.0},
    "claude-sonnet-4-20250514":    {"in": 3.0,  "out": 15.0},
    "claude-sonnet-4-5":           {"in": 3.0,  "out": 15.0},
    "claude-haiku-4-5-20251001":   {"in": 0.8,  "out": 4.0},
}
DEFAULT_PRICING = {"in": 3.0, "out": 15.0}


def estimate_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    pricing = MODEL_PRICING.get(model, DEFAULT_PRICING)
    return (tokens_in * pricing["in"] + tokens_out * pricing["out"]) / 1_000_000