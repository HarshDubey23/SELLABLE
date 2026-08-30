"""Chain reload keeps enriched columns: after a module reload (the repo's own
T30 reset pattern), the in-memory mirror must still carry parent_action_id —
disk always stored it; _load_from_db now re-selects it. Added Phase 2.1.
"""
import importlib

import apps.api.audit.chain as chain


def test_reload_preserves_parent_action_id():
    importlib.reload(chain)                     # fresh chain from disk
    seq = chain.append(
        "executor", "recovery_reasoned",
        {"order_id": "order_test_reload", "parsed_action": "create_payment_link"},
        parent_action_id="aud_999",
        review_state="pending_merchant",
    )
    assert chain.entries()[-1]["parent_action_id"] == "aud_999"

    importlib.reload(chain)                     # the T30 reset pattern
    reloaded = {e["seq"]: e for e in chain.entries()}[seq]
    assert reloaded["parent_action_id"] == "aud_999"
    assert reloaded["review_state"] == "pending_merchant"
    assert chain.verify() is True
