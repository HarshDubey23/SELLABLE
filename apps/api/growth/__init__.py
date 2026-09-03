"""Merchant Growth & Competitive Intelligence Package.

Empowers SELLABLE merchants to grow AOV, attach intelligent cross-sells,
and remain natively transactable by AI buyers using real-world market data.

ARCHITECTURAL INVARIANT:
- External web market data is strictly advisory context and treated as UNTRUSTED.
- Real-world prices and competitor text NEVER override server-side catalog prices.
- All monetary settlements remain governed by the deterministic Policy Gateway (R1-R12).
"""
from .api import router as growth_router

__all__ = ["growth_router"]
