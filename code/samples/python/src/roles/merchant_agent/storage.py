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

"""In-memory storage for cart data, risk data, and the poisoned catalog.

Cart data (merchant-signed JWTs) is persisted between interactions
between the shopper and merchant agents.

The poisoned catalog is loaded once at module initialization from
``data/poisoned_catalog.json``.  Every item defaults to
``availability = False`` (i.e. stock 0) until a drop is triggered via
``POST /trigger-price-drop`` on the trigger server.
"""

import json
import logging
import os
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Catalog helpers
# ---------------------------------------------------------------------------

def _resolve_catalog_path() -> Path:
  """Resolve the path to poisoned_catalog.json.

  Walks up from the merchant_agent package directory until it finds the
  ``data/`` directory that contains ``poisoned_catalog.json``.
  """
  anchor = Path(__file__).resolve().parent
  for _ in range(10):
    candidate = anchor / "data" / "poisoned_catalog.json"
    if candidate.exists():
      return candidate
    anchor = anchor.parent
  # Absolute fallback to repo root
  return Path("data/poisoned_catalog.json")


def _load_poisoned_catalog() -> dict[str, dict[str, Any]]:
  """Load the poisoned catalog from disk and index it by string item ID.

  Each entry is mapped to the native AP2 internal product model format:
    {
      "id":          str(item["id"]),
      "name":        str,
      "price":       float,
      "currency":    str,
      "description": str,
      "image":       str,
      "category":    str,
      "available":   False,   ← default unavailable (drop state)
      "stock":       0,
    }

  ``available`` and ``stock`` are both set to the "drop default" so that the
  existing trigger-server logic can flip them to True / positive with a single
  ``POST /trigger-price-drop?item_id=<id>&stock=<n>`` call.
  """
  catalog_path = _resolve_catalog_path()
  if not catalog_path.exists():
    logging.warning(
        "poisoned_catalog.json not found at %s; catalog will be empty.",
        catalog_path,
    )
    return {}

  try:
    with open(catalog_path, encoding="utf-8") as f:
      raw: list[dict[str, Any]] = json.load(f)
  except (json.JSONDecodeError, OSError) as exc:
    logging.error("Failed to load poisoned_catalog.json: %s", exc)
    return {}

  catalog: dict[str, dict[str, Any]] = {}
  for item in raw:
    item_id = str(item.get("id", ""))
    if not item_id:
      continue
    # Normalise the currency symbol to an ISO code where possible.
    raw_currency = str(item.get("currency", "USD"))
    iso_currency = "USD" if raw_currency.strip() in ("$", "") else raw_currency

    catalog[item_id] = {
        "id": item_id,
        "name": str(item.get("name", "")),
        "price": float(item.get("price", 0.0)),
        "currency": iso_currency,
        "description": str(item.get("description", "")),
        "image": str(item.get("image", "")),
        "category": str(item.get("category", "")),
        # Default to unavailable — the drop trigger flips this.
        "available": False,
        "stock": 0,
    }

  logging.info(
      "Loaded %d items from poisoned_catalog.json (all availability=False).",
      len(catalog),
  )
  return catalog


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

# Keyed by string item ID (str(json["id"])).
PRODUCT_CATALOG: dict[str, dict[str, Any]] = _load_poisoned_catalog()

# General-purpose in-memory store for cart / risk data.
_store: dict[str, Any] = {}


# ---------------------------------------------------------------------------
# Catalog API
# ---------------------------------------------------------------------------

def get_product(item_id: str) -> dict[str, Any] | None:
  """Return the catalog entry for *item_id*, or None if not found."""
  return PRODUCT_CATALOG.get(str(item_id))


def set_product_available(item_id: str, available: bool = True, stock: int = 10) -> bool:
  """Flip the availability flag for a catalog item (native drop trigger).

  This mirrors the same semantic as the trigger-server's
  ``POST /trigger-price-drop?item_id=<id>&stock=<n>`` endpoint — both
  ultimately update the same in-memory record.

  Args:
    item_id: The catalog item ID (string form of the JSON ``id`` field).
    available: New availability state.
    stock: Positive stock count; 0 means unavailable.

  Returns:
    True if the item was found and updated, False otherwise.
  """
  item_id = str(item_id)
  if item_id not in PRODUCT_CATALOG:
    return False
  PRODUCT_CATALOG[item_id]["available"] = available
  PRODUCT_CATALOG[item_id]["stock"] = stock
  logging.info(
      "Drop triggered: item_id=%s available=%s stock=%d", item_id, available, stock
  )
  return True


# ---------------------------------------------------------------------------
# Cart / risk data API (unchanged from original)
# ---------------------------------------------------------------------------

def get_cart_data(cart_id: str) -> dict[str, Any] | None:
  """Get cart data (jwt, hash, item info) by cart ID."""
  return _store.get(cart_id)


def set_cart_data(cart_id: str, data: dict[str, Any]) -> None:
  """Set cart data by cart ID."""
  _store[cart_id] = data


def set_risk_data(context_id: str, risk_data: str) -> None:
  """Set risk data by context ID."""
  _store[context_id] = risk_data


def get_risk_data(context_id: str) -> str | None:
  """Get risk data by context ID."""
  return _store.get(context_id)
