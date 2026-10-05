#!/usr/bin/env python3
"""Unified HTTP + MCP server for the Merchant Payment Processor agent.

Serves two concerns on port 8083:
  - Webhook route   (POST /initiate-payment)
  - FastMCP tools   (StreamableHTTP at /mcp)

The FastMCP app's lifespan is wired into the outer Starlette app so that the
StreamableHTTPSessionManager task group is properly initialized.
"""

import json
import os

from contextlib import asynccontextmanager

import uvicorn

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route

import server as mcp_server  # provides mcp = FastMCP(...)


PORT = int(os.environ.get("MERCHANT_PAYMENT_PROCESSOR_TRIGGER_PORT", "8083"))


# ---------------------------------------------------------------------------
# Webhook route handlers
# ---------------------------------------------------------------------------

async def initiate_payment(request: Request) -> Response:
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
        payment_token = data.get("payment_token")
        checkout_jwt_hash = data.get("checkout_jwt_hash")
        open_checkout_hash = data.get("open_checkout_hash")
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    for field in ["payment_token", "checkout_jwt_hash", "open_checkout_hash"]:
        if not data.get(field):
            return JSONResponse({"error": f"{field} required"}, status_code=400)

    result = await mcp_server.initiate_payment(
        payment_token,
        checkout_jwt_hash,
        open_checkout_hash,
    )
    return Response(
        content=json.dumps(result, default=str),
        media_type="application/json"
    )


async def health(request: Request) -> Response:
    return JSONResponse({
        "status": "ok",
        "endpoints": [
            f"POST http://localhost:{PORT}/initiate-payment",
            f"POST/GET http://localhost:{PORT}/mcp  (StreamableHTTP MCP)",
        ],
    })


# ---------------------------------------------------------------------------
# Build the combined Starlette app with FastMCP lifespan wired in
# ---------------------------------------------------------------------------

mcp_app = mcp_server.mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(app: Starlette):
    """Start the FastMCP session manager task group alongside this app."""
    async with mcp_app.router.lifespan_context(app):
        yield


routes = [
    Route("/initiate-payment", initiate_payment, methods=["POST"]),
    Route("/", health, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    Mount("/mcp", app=mcp_app),
]

app = Starlette(routes=routes, lifespan=lifespan)


if __name__ == "__main__":
    print(
        "Merchant payment processor trigger + MCP server:"
        f" http://localhost:{PORT}/"
    )
    print(f"  MCP StreamableHTTP endpoint: http://localhost:{PORT}/mcp")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
