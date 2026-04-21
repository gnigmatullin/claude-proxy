import os
"""
main.py — Claude API proxy.

Forwards /v1/messages to Anthropic with:
  - IP whitelist
  - allowed-model enforcement
  - daily spend limit
  - per-project tracking via pseudo-keys
  - encrypted real API key
"""

import httpx
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse

import config
import database
from crypto import load_real_key

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("claude-proxy")

# ── Startup ───────────────────────────────────────────────────────────────────
REAL_API_KEY: str = ""


@asynccontextmanager
async def lifespan(app: FastAPI):
    global REAL_API_KEY
    database.init_db()
    REAL_API_KEY = load_real_key()  # prompts for password interactively
    # Clear password from environment immediately after decryption
    os.environ.pop("MASTER_PASSWORD", None)
    log.info("Claude proxy started on port %s", config.PORT)
    log.info("Allowed IPs:    %s", config.ALLOWED_IPS)
    log.info("Allowed models: %s", config.ALLOWED_MODELS)
    log.info("Daily limit:    $%.2f", config.DAILY_LIMIT_USD)
    log.info("Projects:       %s", list(config.PSEUDO_KEYS.values()))
    yield


app = FastAPI(title="Claude API Proxy", lifespan=lifespan)


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def resolve_project(pseudo_key: str) -> str:
    return config.PSEUDO_KEYS.get(pseudo_key, "unknown")


# ── Middleware / Guards ───────────────────────────────────────────────────────

def check_ip(ip: str):
    if ip not in config.ALLOWED_IPS:
        log.warning("Blocked IP: %s", ip)
        raise HTTPException(status_code=403, detail=f"IP not allowed: {ip}")


def check_daily_limit():
    spent = database.get_daily_cost()
    if spent >= config.DAILY_LIMIT_USD:
        log.warning("Daily limit reached: $%.4f / $%.2f", spent, config.DAILY_LIMIT_USD)
        raise HTTPException(
            status_code=429,
            detail=f"Daily limit of ${config.DAILY_LIMIT_USD} reached (spent ${spent:.4f})",
        )


def check_model(model: str):
    if model not in config.ALLOWED_MODELS:
        log.warning("Blocked model: %s", model)
        raise HTTPException(status_code=400, detail=f"Model not allowed: {model}")


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    spent = database.get_daily_cost()
    return {
        "status": "ok",
        "daily_spent_usd": round(spent, 4),
        "daily_limit_usd": config.DAILY_LIMIT_USD,
        "remaining_usd": round(max(0.0, config.DAILY_LIMIT_USD - spent), 4),
    }


@app.get("/stats")
async def stats(day: str | None = None):
    return {
        "day": day or "today",
        "daily_cost_usd": round(database.get_daily_cost(day), 4),
        "daily_limit_usd": config.DAILY_LIMIT_USD,
        "breakdown": database.get_daily_stats(day),
    }


@app.post("/v1/messages")
async def proxy_messages(request: Request):
    client_ip = get_client_ip(request)

    # ── Guards ────────────────────────────────────────────────────────────────
    check_ip(client_ip)
    check_daily_limit()

    # ── Parse request body ────────────────────────────────────────────────────
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    model = body.get("model", "")
    check_model(model)

    # ── Resolve project from pseudo-key ───────────────────────────────────────
    auth_header = request.headers.get("x-api-key", "")
    project = resolve_project(auth_header)

    streaming = body.get("stream", False)

    log.info("→ project=%-12s model=%-35s stream=%s ip=%s",
             project, model, streaming, client_ip)

    # ── Build forwarded headers ───────────────────────────────────────────────
    forward_headers = {
        "x-api-key": REAL_API_KEY,
        "anthropic-version": request.headers.get("anthropic-version", "2023-06-01"),
        "content-type": "application/json",
    }
    if "anthropic-beta" in request.headers:
        forward_headers["anthropic-beta"] = request.headers["anthropic-beta"]

    # ── Forward to Anthropic ──────────────────────────────────────────────────
    url = f"{config.ANTHROPIC_API_URL}/v1/messages"

    if streaming:
        return await _stream(url, forward_headers, body, project, model, client_ip)
    else:
        return await _standard(url, forward_headers, body, project, model, client_ip)


async def _standard(url, headers, body, project, model, client_ip):
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(url, headers=headers, json=body)

    tokens_in = tokens_out = 0
    try:
        data = resp.json()
        usage = data.get("usage", {})
        tokens_in = usage.get("input_tokens", 0)
        tokens_out = usage.get("output_tokens", 0)
    except Exception:
        pass

    cost = config.estimate_cost(model, tokens_in, tokens_out)
    database.log_request(project, model, tokens_in, tokens_out, cost, resp.status_code, client_ip)

    log.info("← status=%s  in=%d  out=%d  cost=$%.5f", resp.status_code, tokens_in, tokens_out, cost)

    return JSONResponse(content=resp.json(), status_code=resp.status_code)


async def _stream(url, headers, body, project, model, client_ip):
    """Stream response back to client, accumulate token counts at the end."""

    async def generator():
        tokens_in = tokens_out = 0
        status_code = 200
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream("POST", url, headers=headers, json=body) as resp:
                status_code = resp.status_code
                async for chunk in resp.aiter_bytes():
                    yield chunk
                    # Parse SSE for usage data in message_delta events
                    try:
                        text = chunk.decode("utf-8", errors="ignore")
                        for line in text.splitlines():
                            if line.startswith("data:"):
                                payload = json.loads(line[5:].strip())
                                if payload.get("type") == "message_start":
                                    u = payload.get("message", {}).get("usage", {})
                                    tokens_in = u.get("input_tokens", 0)
                                elif payload.get("type") == "message_delta":
                                    u = payload.get("usage", {})
                                    tokens_out = u.get("output_tokens", 0)
                    except Exception:
                        pass

        cost = config.estimate_cost(model, tokens_in, tokens_out)
        database.log_request(project, model, tokens_in, tokens_out, cost, status_code, client_ip)
        log.info("← stream  in=%d  out=%d  cost=$%.5f", tokens_in, tokens_out, cost)

    return StreamingResponse(generator(), media_type="text/event-stream")