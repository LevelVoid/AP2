# Copyright 2025 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main for the merchant agent.

In addition to the standard A2A JSON-RPC endpoint, this server exposes a
lightweight HTTP route for triggering the native availability drop:

  POST /drop?item_id=<id>[&stock=<n>]

This is the same drop trigger documented in agent.md Task 1.  The automation
script (``scripts/run_baseline_benchmark.py``) calls this endpoint to flip
``availability = True`` for the item under test.

Example::

  curl -X POST "http://localhost:8001/drop?item_id=168&stock=10"
"""

import json
from collections.abc import Sequence

from absl import app
from common import server
from roles.merchant_agent import tools as merchant_tools
from roles.merchant_agent.agent_executor import MerchantAgentExecutor
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route


AGENT_MERCHANT_PORT = 8001


async def drop_endpoint(request: Request) -> JSONResponse:
  """HTTP endpoint to trigger the native availability drop for a catalog item.

  Query parameters:
    item_id: Required. The catalog item ID (numeric string).
    stock: Optional. Positive integer stock count; defaults to 10.

  Returns:
    JSON with ``{"ok": true, "item_id": ..., "stock": ...}`` on success, or
    ``{"ok": false, "error": ...}`` if the item is not found.
  """
  item_id = request.query_params.get("item_id", "")
  if not item_id:
    return JSONResponse({"ok": False, "error": "item_id required"}, status_code=400)

  stock_str = request.query_params.get("stock", "10")
  try:
    stock = max(1, int(stock_str))
  except ValueError:
    stock = 10

  success = merchant_tools.drop_item(item_id, stock=stock)
  if not success:
    return JSONResponse(
        {"ok": False, "error": f"item_id {item_id!r} not found in catalog"},
        status_code=404,
    )

  return JSONResponse({
      "ok": True,
      "item_id": item_id,
      "stock": stock,
      "message": (
          f"Item {item_id} is now available (stock={stock}). "
          "Shopping agent will see it on the next check_product call."
      ),
  })


def main(argv: Sequence[str]) -> None:
  agent_card = server.load_local_agent_card(__file__)
  extra_routes = [
      Route("/drop", drop_endpoint, methods=["POST", "OPTIONS"]),
  ]
  server.run_agent_blocking(
      port=AGENT_MERCHANT_PORT,
      agent_card=agent_card,
      executor=MerchantAgentExecutor(agent_card.capabilities.extensions),
      rpc_url="/a2a/merchant_agent",
      extra_routes=extra_routes,
  )

if __name__ == "__main__":
  app.run(main)
