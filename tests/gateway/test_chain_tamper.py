"""T30: audit chain — tamper one byte -> verify() False."""
import os, sys, importlib
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import apps.api.audit.chain as chain


def test_T30_chain_tamper_detected():
    importlib.reload(chain)                     # fresh chain
    seq = chain.append("test", "order_created", {"amount_paise": 100})
    assert chain.verify() is True

    _chain = chain.entries()
    _chain[seq]["payload_hash"] = "f" * 64      # flip one entry's payload hash
    assert chain.verify() is False
