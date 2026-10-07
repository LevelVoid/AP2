#!/usr/bin/env python3
"""Unified HTTP + MCP server for the Merchant agent.

Serves two concerns on port 8081:
  - Webhook routes  (POST /trigger-price-drop, GET /state, GET /health)
  - FastMCP tools   (StreamableHTTP at /mcp)

The FastMCP app's lifespan is wired into the outer Starlette app so that the
StreamableHTTPSessionManager task group is properly initialized.
"""

import json
import os
import time

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import uvicorn

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

import server as mcp_module  # provides mcp = FastMCP(...)


_TEMP_DB = Path(os.environ.get("TEMP_DB_DIR", ".temp-db"))
_TRIGGER_STATE_PATH = os.environ.get(
    "MERCHANT_TRIGGER_STATE_PATH",
    str(_TEMP_DB / "merchant_trigger_state.json"),
)

PORT = int(os.environ.get("MERCHANT_TRIGGER_PORT", "8081"))


# ---------------------------------------------------------------------------
# State helpers
# ---------------------------------------------------------------------------

def _load_trigger_state_raw() -> dict[str, Any]:
    if not os.path.exists(_TRIGGER_STATE_PATH):
        return {}
    try:
        with open(_TRIGGER_STATE_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _merge_trigger_state(
    item_id: str, value: float | dict[str, Any]
) -> dict[str, Any]:
    state = _load_trigger_state_raw()
    state[item_id] = value
    os.makedirs(os.path.dirname(_TRIGGER_STATE_PATH), exist_ok=True)
    with open(_TRIGGER_STATE_PATH, "w") as f:
        json.dump(state, f, indent=2)
    return state


# ---------------------------------------------------------------------------
# Webhook route handlers
# ---------------------------------------------------------------------------

async def trigger_price_drop(request: Request) -> Response:
    qs = parse_qs(urlparse(str(request.url)).query)
    item_id = (qs.get("item_id") or [None])[0]
    if not item_id:
        return JSONResponse({"error": "item_id required"}, status_code=400)

    price_str = (qs.get("price") or ["5.0"])[0]
    price = float(price_str)
    stock_str = (qs.get("stock") or [None])[0]
    payload: dict[str, Any] = {"price": price, "_touch": time.time()}
    if stock_str is not None:
        payload["stock"] = max(0, int(stock_str))
    _merge_trigger_state(item_id, payload)
    stock_msg = f", stock {payload['stock']}" if "stock" in payload else ""
    return JSONResponse({
        "ok": True,
        "item_id": item_id,
        "price": price,
        **( {"stock": payload["stock"]} if "stock" in payload else {}),
        "message": (
            f"Price for {item_id} set to ${price}{stock_msg}. Shopping agent"
            " sees it on next check_product (web UI may nudge immediately"
            " via /state poll)."
        ),
    })


async def state_handler(request: Request) -> Response:
    qs = parse_qs(urlparse(str(request.url)).query)
    item_id = (qs.get("item_id") or [None])[0]
    if not item_id:
        return JSONResponse({"error": "item_id required"}, status_code=400)
    raw = _load_trigger_state_raw()
    return JSONResponse({"item_id": item_id, "entry": raw.get(item_id)})


async def reset_state(request: Request) -> Response:
    """Clear trigger + inventory so the next benchmark iteration starts clean.

    Does not delete signing keys. Safe to call between iterations while the
    merchant MCP process is still running — trigger state is re-read from disk
    on every check_product; inventory overlay forces catalog poison regardless
    of stale in-memory entries.
    """
    os.makedirs(os.path.dirname(_TRIGGER_STATE_PATH) or '.', exist_ok=True)
    with open(_TRIGGER_STATE_PATH, 'w') as f:
        json.dump({}, f)
    inv_path = os.environ.get(
        'MERCHANT_INVENTORY_PATH',
        str(_TEMP_DB / 'merchant_inventory.json'),
    )
    try:
        with open(inv_path, 'w') as f:
            json.dump({}, f)
    except OSError:
        pass
    # Clear in-process inventory cache when merchant MCP shares this process
    try:
        mcp_module._TEMP_INVENTORY.clear()
    except Exception:
        pass
    return JSONResponse({'ok': True, 'message': 'trigger + inventory reset'})


async def health(request: Request) -> Response:
    return JSONResponse({
        "status": "ok",
        "endpoints": [
            f"POST http://localhost:{PORT}/trigger-price-drop"
            "?item_id=<item_id>&price=<price>[&stock=<stock>]",
            f"GET  http://localhost:{PORT}/state?item_id=<item_id>",
            f"POST http://localhost:{PORT}/reset-state",
            f"POST/GET http://localhost:{PORT}/mcp  (StreamableHTTP MCP)",
        ],
    })


# ---------------------------------------------------------------------------
# Build the combined Starlette app with FastMCP lifespan wired in
# ---------------------------------------------------------------------------

mcp_app = mcp_module.mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(app: Starlette):
    """Start the FastMCP session manager task group alongside this app."""
    async with mcp_app.router.lifespan_context(app):
        yield


from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

routes = [
    Route("/trigger-price-drop", trigger_price_drop, methods=["POST", "OPTIONS"]),
    Route("/state", state_handler, methods=["GET", "OPTIONS"]),
    Route("/reset-state", reset_state, methods=["POST", "OPTIONS"]),
    Route("/", health, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    Mount("/mcp", app=mcp_app),
]

app = Starlette(
    routes=routes,
    lifespan=lifespan,
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    ]
)


if __name__ == "__main__":
    print(f"Merchant trigger + MCP server: http://localhost:{PORT}/")
    print(f"  MCP StreamableHTTP endpoint: http://localhost:{PORT}/mcp")
    print(f"  State file: {_TRIGGER_STATE_PATH}")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
