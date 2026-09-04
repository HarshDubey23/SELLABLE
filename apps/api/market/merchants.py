"""The three merchants, and the signed manifests that bound them.

A capability manifest is a merchant's declared limits: how much it may
discount, when it may ship free, how fast it can deliver, what warranty it
sells, what it holds in stock, and the cost basis below which it will not
trade. It is signed with the same HMAC the gateway already uses for
missions, so a manifest that has been edited — by a compromised merchant
process, by a tampered database row, by anyone — fails verification and
every offer under it is refused.

The point of signing it is not that we expect the file to be attacked. It
is that "the merchant cannot offer 15% when its cap is 8%" is only true
if the 8% is itself trustworthy. Otherwise the policy engine is checking
a number the attacker supplied against a number the attacker also
supplied.

Seeding is idempotent and versioned: re-running it never duplicates a
merchant, and bumping `MANIFEST_VERSION` re-signs and replaces the stored
rows so a manifest change cannot half-apply.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, replace
from typing import Any

from ..gateway import mission_verify
from ..store import db as store

# Bump when the shape or the numbers change. Seeding replaces every row
# whose version differs, so a partially-migrated set cannot exist.
MANIFEST_VERSION = 3

LLM_BACKED = "llm"
SCRIPTED = "scripted"


@dataclass(frozen=True)
class CapabilityManifest:
    """What one merchant is permitted to offer. Signed; never trusted raw."""

    merchant_id: str
    display_name: str
    strategy: str                    # the merchant's own commercial posture
    strategy_brief: str              # what its model is told to optimise for

    max_line_discount_pct: int
    max_bundle_discount_pct: int
    bundle_min_items: int            # bundle discount needs this many lines
    free_ship_threshold_paise: int   # FREE shipping only at or above this
    standard_ship_paise: int
    min_delivery_days: int           # cannot promise faster than it can ship
    max_delivery_days: int
    allowed_warranty_years: tuple[int, ...]
    warranty_price_per_year_paise: int
    cost_basis_pct: int              # what the goods cost it, as % of list
    min_margin_pct: int              # it will not trade below this margin
    eligible_categories: tuple[str, ...]
    version: int = MANIFEST_VERSION
    signature: str = ""

    def unsigned(self) -> dict[str, Any]:
        """Every field except the signature, in a stable order."""
        d = {
            "merchant_id": self.merchant_id,
            "display_name": self.display_name,
            "strategy": self.strategy,
            "strategy_brief": self.strategy_brief,
            "max_line_discount_pct": self.max_line_discount_pct,
            "max_bundle_discount_pct": self.max_bundle_discount_pct,
            "bundle_min_items": self.bundle_min_items,
            "free_ship_threshold_paise": self.free_ship_threshold_paise,
            "standard_ship_paise": self.standard_ship_paise,
            "min_delivery_days": self.min_delivery_days,
            "max_delivery_days": self.max_delivery_days,
            "allowed_warranty_years": list(self.allowed_warranty_years),
            "warranty_price_per_year_paise": self.warranty_price_per_year_paise,
            "cost_basis_pct": self.cost_basis_pct,
            "min_margin_pct": self.min_margin_pct,
            "eligible_categories": list(self.eligible_categories),
            "version": self.version,
        }
        return d

    def signed(self) -> CapabilityManifest:
        blob = json.dumps(self.unsigned(), sort_keys=True, separators=(",", ":"))
        return replace(self, signature=mission_verify.sign_mission(blob))

    def signature_valid(self) -> bool:
        if not self.signature:
            return False
        blob = json.dumps(self.unsigned(), sort_keys=True, separators=(",", ":"))
        try:
            return bool(mission_verify.verify_mission(blob, self.signature))
        except Exception:
            return False


# ---------------------------------------------------------------------
# The three. Their numbers differ because their commercial positions do —
# that is what makes the negotiation produce different offers rather than
# three colours of the same one.
# ---------------------------------------------------------------------
_SEED: tuple[CapabilityManifest, ...] = (
    CapabilityManifest(
        merchant_id="NOVATECH",
        display_name="NovaTech",
        strategy="margin and conversion",
        strategy_brief=(
            "You protect margin. You would rather lose a sale than discount "
            "deeply, so you compete on speed, warranty and included extras "
            "before you compete on price. You ship fast because you hold "
            "stock."),
        max_line_discount_pct=8,
        max_bundle_discount_pct=10,
        bundle_min_items=3,
        free_ship_threshold_paise=200000,
        standard_ship_paise=9900,
        min_delivery_days=1,
        max_delivery_days=5,
        allowed_warranty_years=(0, 1, 2),
        warranty_price_per_year_paise=19900,
        cost_basis_pct=72,
        min_margin_pct=18,
        eligible_categories=("cricket", "electronics", "books", "apparel",
                             "stationery", "groceries"),
    ),
    CapabilityManifest(
        merchant_id="GEARHUB",
        display_name="GearHub",
        strategy="win new customers",
        strategy_brief=(
            "You are buying market share. You discount harder than anyone "
            "and you throw in free shipping early, because a first order "
            "matters more to you than this order's margin. You are slower "
            "to deliver because you drop-ship."),
        max_line_discount_pct=15,
        max_bundle_discount_pct=18,
        bundle_min_items=2,
        free_ship_threshold_paise=100000,
        standard_ship_paise=7900,
        min_delivery_days=3,
        max_delivery_days=9,
        allowed_warranty_years=(0, 1),
        warranty_price_per_year_paise=14900,
        cost_basis_pct=80,
        min_margin_pct=8,
        eligible_categories=("cricket", "electronics", "apparel", "books",
                             "stationery", "groceries"),
    ),
    CapabilityManifest(
        merchant_id="BYTECART",
        display_name="ByteCart",
        strategy="clear inventory",
        strategy_brief=(
            "You are sitting on stock you need gone. You bundle aggressively "
            "and add extras to move units, but your per-line discount is "
            "capped tightly because your buying was expensive. Delivery is "
            "middling."),
        max_line_discount_pct=6,
        max_bundle_discount_pct=22,
        bundle_min_items=3,
        free_ship_threshold_paise=150000,
        standard_ship_paise=8900,
        min_delivery_days=2,
        max_delivery_days=7,
        allowed_warranty_years=(0, 1, 2, 3),
        warranty_price_per_year_paise=9900,
        cost_basis_pct=76,
        min_margin_pct=10,
        eligible_categories=("cricket", "electronics", "books", "apparel",
                             "stationery", "groceries"),
    ),
)


def ensure_schema() -> None:
    store.execute(
        "CREATE TABLE IF NOT EXISTS market_merchants ("
        " merchant_id TEXT PRIMARY KEY,"
        " version INTEGER NOT NULL,"
        " manifest_json TEXT NOT NULL,"
        " signature TEXT NOT NULL,"
        " seeded_at INTEGER NOT NULL)"
    )


def seed(force: bool = False) -> list[str]:
    """Sign and store the manifests. Idempotent; returns what it wrote.

    A row whose version differs from MANIFEST_VERSION is replaced rather
    than left alongside, so the store can never hold two generations of
    the same merchant's limits.
    """
    import time as _time

    ensure_schema()
    written: list[str] = []
    for manifest in _SEED:
        row = store.query_one(
            "SELECT version FROM market_merchants WHERE merchant_id = ?",
            (manifest.merchant_id,))
        if row is not None and row["version"] == MANIFEST_VERSION and not force:
            continue
        s = manifest.signed()
        store.execute(
            "INSERT OR REPLACE INTO market_merchants "
            "(merchant_id, version, manifest_json, signature, seeded_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (s.merchant_id, MANIFEST_VERSION,
             json.dumps(s.unsigned(), sort_keys=True, separators=(",", ":")),
             s.signature, int(_time.time())))
        written.append(s.merchant_id)
    return written


def _from_row(row: dict[str, Any]) -> CapabilityManifest:
    d = json.loads(row["manifest_json"])
    return CapabilityManifest(
        merchant_id=d["merchant_id"],
        display_name=d["display_name"],
        strategy=d["strategy"],
        strategy_brief=d["strategy_brief"],
        max_line_discount_pct=d["max_line_discount_pct"],
        max_bundle_discount_pct=d["max_bundle_discount_pct"],
        bundle_min_items=d["bundle_min_items"],
        free_ship_threshold_paise=d["free_ship_threshold_paise"],
        standard_ship_paise=d["standard_ship_paise"],
        min_delivery_days=d["min_delivery_days"],
        max_delivery_days=d["max_delivery_days"],
        allowed_warranty_years=tuple(d["allowed_warranty_years"]),
        warranty_price_per_year_paise=d["warranty_price_per_year_paise"],
        cost_basis_pct=d["cost_basis_pct"],
        min_margin_pct=d["min_margin_pct"],
        eligible_categories=tuple(d["eligible_categories"]),
        version=d["version"],
        signature=row["signature"],
    )


def all_manifests() -> list[CapabilityManifest]:
    seed()
    return [_from_row(r) for r in store.query(
        "SELECT * FROM market_merchants ORDER BY merchant_id")]


def get(merchant_id: str) -> CapabilityManifest | None:
    seed()
    row = store.query_one(
        "SELECT * FROM market_merchants WHERE merchant_id = ?", (merchant_id,))
    return _from_row(row) if row else None


def public_view(m: CapabilityManifest, *, mode: str) -> dict[str, Any]:
    """What a reader is shown about a merchant.

    Its own limits, because a reviewer needs them to judge whether a
    refusal was correct. Never another merchant's — that view is assembled
    per merchant and the caller passes exactly one.
    """
    return {
        "merchant_id": m.merchant_id,
        "display_name": m.display_name,
        "strategy": m.strategy,
        "max_line_discount_pct": m.max_line_discount_pct,
        "max_bundle_discount_pct": m.max_bundle_discount_pct,
        "bundle_min_items": m.bundle_min_items,
        "free_ship_threshold_paise": m.free_ship_threshold_paise,
        "delivery_days_range": [m.min_delivery_days, m.max_delivery_days],
        "allowed_warranty_years": list(m.allowed_warranty_years),
        "min_margin_pct": m.min_margin_pct,
        "manifest_version": m.version,
        "manifest_signature_valid": m.signature_valid(),
        # Honest labelling, everywhere it is displayed.
        "agent_mode": mode,
        "agent_mode_label": ("LLM merchant" if mode == LLM_BACKED
                             else "scripted fallback merchant"),
    }
