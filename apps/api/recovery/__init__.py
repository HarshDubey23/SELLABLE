"""Executor-side payment recovery.

These modules live outside `apps/api/agent/` on purpose. Recovering a
failed or ambiguous payment means talking to the money boundary, and the
buyer agent is not allowed to do that — it is an HTTP client of the
storefront, exactly like any third-party agent would be.

Putting recovery here makes that a structural fact rather than a
convention: `tests/invariants/test_agent_custody.py` asserts that nothing
under `agent/` imports `razorpay_client`, and this package is where the
code that legitimately needs it now lives.
"""
