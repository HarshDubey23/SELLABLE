"""Day 5 catalog extension: floor and ceiling prices per SKU.

Add these to apps/api/products.py CATALOG entries. The floor is the
merchant's walk-away price (typically 70-85% of list price). The ceiling
is the MSRP (= list price). The negotiation engine reads these to bound
offers.

Patch format: for each SKU in CATALOG, add two fields:
  floor_paise: int   # merchant walk-away (e.g., 0.80 * price_paise)
  ceiling_paise: int # MSRP (= price_paise)

This file is a DROP-IN PATCH. Apply by merging the FLOOR_CEILING dict
into CATALOG at load time (see products.py patch below).
"""
from __future__ import annotations

FLOOR_CEILING = {
    "BAT-001": {"floor_paise": 119900, "ceiling_paise": 149900},
    "BAT-002": {"floor_paise": 199900, "ceiling_paise": 249900},
    "BALL-001": {"floor_paise": 71900, "ceiling_paise": 89900},
    "BALL-002": {"floor_paise": 27900, "ceiling_paise": 34900},
    "PAD-001": {"floor_paise": 79900, "ceiling_paise": 99900},
    "GLOVE-001": {"floor_paise": 55900, "ceiling_paise": 69900},
    "GRIP-001": {"floor_paise": 23900, "ceiling_paise": 29900},
    "KIT-001": {"floor_paise": 359900, "ceiling_paise": 449900},
    "BOOK-001": {"floor_paise": 31900, "ceiling_paise": 39900},
    "BOOK-002": {"floor_paise": 23900, "ceiling_paise": 29900},
    "BOOK-003": {"floor_paise": 27900, "ceiling_paise": 34900},
    "BOOK-004": {"floor_paise": 35900, "ceiling_paise": 44900},
    "BOOK-005": {"floor_paise": 31900, "ceiling_paise": 39900},
    "BOOK-006": {"floor_paise": 34300, "ceiling_paise": 42900},
    "BOOK-007": {"floor_paise": 23900, "ceiling_paise": 29900},
    "BOOK-008": {"floor_paise": 27900, "ceiling_paise": 34900},
    "EAR-001": {"floor_paise": 103900, "ceiling_paise": 129900},
    "EAR-002": {"floor_paise": 279900, "ceiling_paise": 349900},
    "CHG-001": {"floor_paise": 79900, "ceiling_paise": 99900},
    "CBL-001": {"floor_paise": 23900, "ceiling_paise": 29900},
    "PWR-001": {"floor_paise": 119900, "ceiling_paise": 149900},
    "LAP-001": {"floor_paise": 2560000, "ceiling_paise": 3200000},
    "LAP-002": {"floor_paise": 359900, "ceiling_paise": 449900},
    "TSH-001": {"floor_paise": 39900, "ceiling_paise": 49900},
    "TSH-002": {"floor_paise": 55900, "ceiling_paise": 69900},
    "JOG-001": {"floor_paise": 71900, "ceiling_paise": 89900},
    "HOOD-001": {"floor_paise": 103900, "ceiling_paise": 129900},
    "SNEK-001": {"floor_paise": 119900, "ceiling_paise": 149900},
    "SOCK-001": {"floor_paise": 23900, "ceiling_paise": 29900},
    "RICE-001": {"floor_paise": 39900, "ceiling_paise": 49900},
    "OIL-001": {"floor_paise": 31900, "ceiling_paise": 39900},
    "TEA-001": {"floor_paise": 19900, "ceiling_paise": 24900},
    "HONY-001": {"floor_paise": 27900, "ceiling_paise": 34900},
    "SNCK-001": {"floor_paise": 35900, "ceiling_paise": 44900},
    "NOTE-001": {"floor_paise": 23900, "ceiling_paise": 29900},
    "PEN-001": {"floor_paise": 15900, "ceiling_paise": 19900},
    "MRKR-001": {"floor_paise": 19900, "ceiling_paise": 24900},
    "STKY-001": {"floor_paise": 11900, "ceiling_paise": 14900},
    "BAGP-001": {"floor_paise": 79900, "ceiling_paise": 99900},
    "PLNR-001": {"floor_paise": 31900, "ceiling_paise": 39900},
}


def apply_floor_ceiling(catalog: dict) -> dict:
    """Merge FLOOR_CEILING into a CATALOG dict. Returns the mutated catalog.

    If a SKU is in FLOOR_CEILING, add floor_paise + ceiling_paise.
    Otherwise derive defaults: floor = 80% of price, ceiling = price.
    """
    for sku, p in catalog.items():
        if sku in FLOOR_CEILING:
            p["floor_paise"] = FLOOR_CEILING[sku]["floor_paise"]
            p["ceiling_paise"] = FLOOR_CEILING[sku]["ceiling_paise"]
        else:
            p["floor_paise"] = int(p["price_paise"] * 0.80)
            p["ceiling_paise"] = p["price_paise"]
    return catalog
