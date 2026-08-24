"""Gateway contracts. Pure stdlib — no FastAPI, no network, no I/O."""
from dataclasses import dataclass
from enum import Enum
import hashlib
import json
from typing import Optional, Tuple


class Decision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


@dataclass(frozen=True)
class Mission:
    mission_id: str
    intent: str
    budget_paise: int
    allowed_categories: Tuple[str, ...]
    forbidden_categories: Tuple[str, ...]
    upsell_cap: float          # e.g. 1.3 => max spend 1.3x budget
    expires_at: int            # unix seconds
    signature: str = ""


@dataclass(frozen=True)
class ProposalItem:
    sku: str
    qty: int
    price_paise: int           # price as claimed by the proposer (R3 checks this)


@dataclass(frozen=True)
class Proposal:
    mission_id: str
    items: Tuple[ProposalItem, ...]
    justification: str = ""


@dataclass(frozen=True)
class Violation:
    rule_id: str               # R1_BUDGET, R10_EXPIRY, ...
    message: str               # human-readable reason
    attempted_value: Optional[int] = None
    limit_value: Optional[int] = None
    hint: str = ""


@dataclass(frozen=True)
class Verdict:
    decision: Decision
    rule_id: Optional[str]     # None on APPROVE
    reason: str
    proposal_hash: Optional[str]
    seq: Optional[int]


def canonical_json(obj) -> str:
    """Sorted keys, no whitespace — deterministic hashes."""
    return json.dumps(_plain(obj), sort_keys=True, separators=(",", ":"))


def _plain(obj):
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _plain(v) for k, v in vars(obj).items()}
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_plain(v) for v in obj]
    return obj


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()
