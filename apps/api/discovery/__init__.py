"""Real-World Live Web Discovery Pipeline.

Provides live product search, web scraping, multi-source listing extraction,
untrusted data verification & normalization, multi-merchant comparison,
recommendation synthesis, and deterministic Policy Gateway validation.

INVARIANTS:
- All web pages, titles, and snippets are treated as UNTRUSTED input.
- Web data is strictly ADVISORY: it informs comparison and reasoning.
- External web claims never override server-side catalog prices or bypass R1-R12 rules.
"""
from .api import router as discovery_router
from .pipeline import DiscoveryPipelineResult, run_real_product_discovery

__all__ = ["discovery_router", "run_real_product_discovery", "DiscoveryPipelineResult"]
