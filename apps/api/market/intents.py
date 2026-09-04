"""What a merchant is allowed to say.

THE ARGUMENT THIS FILE IS
-------------------------
SELLABLE's thesis is that a model cannot decide what money moves, and the
way that is enforced everywhere else is by vocabulary: the buyer agent
proposes a SKU and a quantity, and there is no message it can send that
means "pay ₹50,000".

Merchants get the same treatment. A merchant may offer a discount
*percentage*, free shipping, a faster delivery, an add-on, a longer
warranty — every lever a real merchant actually has. It may not state a
price, because `OfferIntent` has nowhere to put one. The total is
computed by `policy.py` from the server-side catalog and the merchant's
own signed manifest, and that computation is the only thing downstream
ever sees.

So a compromised merchant model, a prompt-injected product description,
or a provider returning attacker-chosen JSON cannot express an amount.
Not "is rejected when it does" — cannot express one. The difference
matters: a rejection is a check you can forget to run.

`tests/invariants/test_market_isolation.py` parses this file and fails
the build if a field appears that could carry a price.
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

# Every field name OfferIntent is permitted to have. The invariant test
# compares the model's real fields against this and fails on any addition,
# so widening the merchant vocabulary is a deliberate act with a diff,
# never something that arrives by accident inside a refactor.
ALLOWED_INTENT_FIELDS = frozenset({
    "merchant_id", "basket_sku_set", "line_discount_pct",
    "bundle_discount_pct", "shipping", "delivery_days", "addon_skus",
    "warranty_years", "round", "in_reply_to", "offer_id", "rationale",
})

# Substrings that would indicate a price crept into the schema. Checked
# against field names by the invariant test.
FORBIDDEN_FIELD_SUBSTRINGS = (
    "amount", "price", "paise", "total", "rupee", "inr", "cost", "fee",
    "charge", "payable", "sum",
)

Shipping = Literal["FREE", "STANDARD"]

_SKU_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{1,31}$")
_ID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,64}$")


class OfferIntent(BaseModel):
    """One merchant's offer, expressed only in levers it is allowed to pull.

    Note what is absent. There is no amount, no price, no total, and no
    currency. A merchant that wants to be cheaper says so with
    `line_discount_pct`, and the policy engine decides whether its manifest
    permits that and what the resulting figure is.
    """

    model_config = {"extra": "forbid", "frozen": True}

    merchant_id: str = Field(min_length=1, max_length=64)
    basket_sku_set: tuple[str, ...] = Field(min_length=1, max_length=24)
    line_discount_pct: int = Field(ge=0, le=100)
    bundle_discount_pct: int = Field(ge=0, le=100)
    shipping: Shipping
    delivery_days: int = Field(ge=0, le=90)
    addon_skus: tuple[str, ...] = Field(default=(), max_length=12)
    warranty_years: int = Field(ge=0, le=10)
    round: int = Field(ge=1, le=10)
    in_reply_to: str | None = Field(default=None, max_length=64)
    offer_id: str = Field(min_length=4, max_length=64)

    # Free text the merchant model writes to explain itself. It is shown to
    # the buyer and to the reader, and it is data — never instruction. It
    # never reaches the policy engine's arithmetic.
    rationale: str = Field(default="", max_length=400)

    @field_validator("merchant_id", "offer_id", "in_reply_to")
    @classmethod
    def _identifier(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _ID_RE.match(v):
            raise ValueError("identifier must be 1-64 chars of [A-Za-z0-9_-]")
        return v

    @field_validator("basket_sku_set", "addon_skus")
    @classmethod
    def _skus(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for sku in v:
            if not _SKU_RE.match(sku):
                raise ValueError(f"{sku!r} is not a well-formed SKU")
        if len(set(v)) != len(v):
            raise ValueError("duplicate SKU in list")
        return v

    @field_validator("rationale")
    @classmethod
    def _rationale_is_data(cls, v: str) -> str:
        """Strip control characters. Everything else is kept verbatim.

        Deliberately NOT an injection filter. Trying to detect "ignore all
        previous instructions" in prose is a losing game, and a system that
        depends on winning it is one clever phrasing from failure. The
        defence is that this string never reaches an arithmetic path and
        never becomes an instruction to anything that can spend — see the
        module docstring. It is quoted back to the reader as-is, because
        showing the attempt is more useful than hiding it.
        """
        return "".join(ch for ch in v if ch == "\n" or ch >= " ")

    def canonical(self) -> dict[str, Any]:
        """Stable ordering, for hashing into the negotiation transcript."""
        return {
            "merchant_id": self.merchant_id,
            "basket_sku_set": sorted(self.basket_sku_set),
            "line_discount_pct": self.line_discount_pct,
            "bundle_discount_pct": self.bundle_discount_pct,
            "shipping": self.shipping,
            "delivery_days": self.delivery_days,
            "addon_skus": sorted(self.addon_skus),
            "warranty_years": self.warranty_years,
            "round": self.round,
            "in_reply_to": self.in_reply_to,
            "offer_id": self.offer_id,
            "rationale": self.rationale,
        }


# The buyer's whole vocabulary for pushing back. Note what is not in it:
# there is no way to ask for a number, only for a direction.
BuyerAsk = Literal["FASTER_DELIVERY", "LOWER_PRICE", "LONGER_WARRANTY",
                   "FREE_SHIPPING", "MORE_INCLUDED"]


class BuyerCounter(BaseModel):
    """One targeted request from the buyer to exactly one merchant.

    `merchant_id` is the only merchant this is sent to, and the ask is a
    named dimension rather than free text about what a competitor offered.
    That is what keeps merchant isolation true at the protocol level
    instead of by convention: there is no field here that could carry a
    rival's terms.
    """

    model_config = {"extra": "forbid", "frozen": True}

    merchant_id: str = Field(min_length=1, max_length=64)
    ask: BuyerAsk
    round: int = Field(ge=1, le=10)
    note: str = Field(default="", max_length=200)

    @field_validator("note")
    @classmethod
    def _note_is_data(cls, v: str) -> str:
        return "".join(ch for ch in v if ch == "\n" or ch >= " ")
