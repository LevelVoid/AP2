#!/usr/bin/env python3
"""Unified HTTP + MCP server for the Credential Provider agent.

Serves two concerns on port 8082:
  - Webhook route   (POST /payment-receipt)
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


PORT = int(os.environ.get("CREDENTIALS_PROVIDER_TRIGGER_PORT", "8082"))


# ---------------------------------------------------------------------------
# Webhook route handlers
# ---------------------------------------------------------------------------

async def payment_receipt(request: Request) -> Response:
    try:
        body = await request.body()
        data = json.loads(body) if body else {}
        payment_receipt_val = data.get("payment_receipt")
    except json.JSONDecodeError:
        return JSONResponse({"error": "invalid JSON"}, status_code=400)

    if not payment_receipt_val:
        return JSONResponse({"error": "payment_receipt required"}, status_code=400)

    print(f"[trigger] Received payment receipt: {str(payment_receipt_val)[:20]}...")
    mcp_server.verify_payment_receipt(payment_receipt_val)
    return JSONResponse({"status": "ok"})


async def health(request: Request) -> Response:
    return JSONResponse({
        "status": "ok",
        "endpoints": [
            f"POST http://localhost:{PORT}/payment-receipt",
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
    Route("/payment-receipt", payment_receipt, methods=["POST"]),
    Route("/", health, methods=["GET"]),
    Route("/health", health, methods=["GET"]),
    Mount("/mcp", app=mcp_app),
]

app = Starlette(routes=routes, lifespan=lifespan)


if __name__ == "__main__":
    print(
        "Credentials provider trigger + MCP server:"
        f" http://localhost:{PORT}/"
    )
    print(f"  MCP StreamableHTTP endpoint: http://localhost:{PORT}/mcp")
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
