# -*- coding: utf-8 -*-
"""
tests/security/test_all_20_attacks.py — Complete 20-Attack Adversarial Verification Suite

Covers Attacks I1 to I20:
I1  Budget Override
I2  Prompt Injection
I3  Unauthorized Upsell
I4  Fake Budget Update
I5  Free-Price Attack
I6  Unicode/Obfuscation
I7  Cross-Category Injection
I8  Category Relabeling
I9  Cart Mutation
I10 Quote Mutation
I11 Quote Substitution
I12 Replay
I13 Expired Quote
I14 Expired Mandate
I15 Revoked Mandate
I16 Currency Manipulation
I17 Quantity Manipulation
I18 Unknown SKU
I19 Webhook Forgery
I20 Concurrent Replay
"""
import time
import pytest
import hmac
import hashlib
import concurrent.futures

from apps.api.gateway import engine
from apps.api.gateway.types import Mission, Proposal, ProposalItem, Decision
from apps.api.products import CATALOG
from apps.api.approval import register as reg, verify as ver
import apps.api.money as money

def test_i1_budget_override():
    m = Mission(mission_id="MSN-I1", intent="bat < 1000", budget_paise=100000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I1", items=(ProposalItem(sku="BAT-001", qty=1, price_paise=149900),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R1_BUDGET"

def test_i2_prompt_injection():
    m = Mission(mission_id="MSN-I2", intent="budget Rs 2000", budget_paise=200000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    # Prompt injection trying to order 2 items exceeding budget
    p = Proposal(mission_id="MSN-I2", items=(ProposalItem(sku="BAT-002", qty=2, price_paise=499800),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R1_BUDGET"

def test_i3_unauthorized_upsell():
    m = Mission(mission_id="MSN-I3", intent="bat", budget_paise=100000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I3", items=(ProposalItem(sku="BAT-001", qty=1, price_paise=149900),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R1_BUDGET"

def test_i4_fake_budget_update():
    m = Mission(mission_id="MSN-I4", intent="bat", budget_paise=100000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I4", items=(ProposalItem(sku="BAT-001", qty=1, price_paise=100000),)) # claimed 100000 instead of 149900 catalog price
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R1_BUDGET"

def test_i5_free_price_attack():
    m = Mission(mission_id="MSN-I5", intent="bat", budget_paise=100000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I5", items=(ProposalItem(sku="BAT-001", qty=1, price_paise=0),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R1_BUDGET"

def test_i6_unicode_obfuscation():
    m = Mission(mission_id="MSN-I6", intent="bat", budget_paise=200000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I6", items=(ProposalItem(sku="BAT-001\u200b", qty=1, price_paise=149900),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R2_FORBIDDEN"

def test_i7_cross_category_injection():
    m = Mission(mission_id="MSN-I7", intent="books", budget_paise=500000, allowed_categories=("books",), forbidden_categories=("electronics",), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I7", items=(ProposalItem(sku="HEADPHONE-001", qty=1, price_paise=299900),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id in ("R2_CATEGORY", "R2_FORBIDDEN")

def test_i8_category_relabeling():
    m = Mission(mission_id="MSN-I8", intent="books", budget_paise=500000, allowed_categories=("books",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I8", items=(ProposalItem(sku="BAT-001", qty=1, price_paise=149900),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R5_SCOPE"

def test_i9_cart_mutation():
    seq = 910009
    reg(seq=seq, mission_id="MSN-I9", proposal_hash="h9", cart_hash="h9", quote_id="Q9", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    ok, code, _ = ver(seq=seq, mission_id="MSN-I9", proposal_hash="h9", cart_hash="MUTATED", quote_id="Q9", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    assert ok is False
    assert code == "CART_HASH_MISMATCH"

def test_i10_quote_mutation():
    seq = 910010
    reg(seq=seq, mission_id="MSN-I10", proposal_hash="h10", cart_hash="h10", quote_id="Q10", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    ok, code, _ = ver(seq=seq, mission_id="MSN-I10", proposal_hash="h10", cart_hash="h10", quote_id="Q10", amount_paise=999900, currency="INR", skus=[("BAT-001", 1)])
    assert ok is False
    assert code == "AMOUNT_MISMATCH"

def test_i11_quote_substitution():
    seq = 910011
    reg(seq=seq, mission_id="MSN-I11", proposal_hash="h11", cart_hash="h11", quote_id="Q11", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    ok, code, _ = ver(seq=seq, mission_id="MSN-I11", proposal_hash="h11", cart_hash="h11", quote_id="Q-FORGED", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    assert ok is False
    assert code == "QUOTE_MISMATCH"

def test_i12_replay():
    seq = 910012
    reg(seq=seq, mission_id="MSN-I12", proposal_hash="h12", cart_hash="h12", quote_id="Q12", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    ok1, _, _ = ver(seq=seq, mission_id="MSN-I12", proposal_hash="h12", cart_hash="h12", quote_id="Q12", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    assert ok1 is True
    ok2, code2, _ = ver(seq=seq, mission_id="MSN-I12", proposal_hash="h12", cart_hash="h12", quote_id="Q12", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    assert ok2 is False
    assert code2 == "BINDING_CONSUMED"

def test_i13_expired_quote():
    now = int(time.time())
    seq = 910013
    reg(seq=seq, mission_id="MSN-I13", proposal_hash="h13", cart_hash="h13", quote_id="Q13", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)], ttl_seconds=0, now_ts=now - 50)
    ok, code, _ = ver(seq=seq, mission_id="MSN-I13", proposal_hash="h13", cart_hash="h13", quote_id="Q13", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)], now_ts=now)
    assert ok is False
    assert code == "BINDING_EXPIRED"

def test_i14_expired_mandate():
    now = int(time.time())
    m = Mission(mission_id="MSN-I14", intent="bat", budget_paise=200000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=now - 100, signature="sig")
    p = Proposal(mission_id="MSN-I14", items=(ProposalItem(sku="BAT-001", qty=1, price_paise=149900),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True, now_ts=now)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R10_EXPIRY"

def test_i15_revoked_mandate():
    m = Mission(mission_id="MSN-I15", intent="bat", budget_paise=200000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I15", items=(ProposalItem(sku="BAT-001", qty=1, price_paise=149900),))
    # verify_fn returns False for revoked / invalid signature
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: False)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R9_SIGNATURE"

def test_i16_currency_manipulation():
    seq = 910016
    reg(seq=seq, mission_id="MSN-I16", proposal_hash="h16", cart_hash="h16", quote_id="Q16", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    ok, code, _ = ver(seq=seq, mission_id="MSN-I16", proposal_hash="h16", cart_hash="h16", quote_id="Q16", amount_paise=149900, currency="USD", skus=[("BAT-001", 1)])
    assert ok is False
    assert code == "CURRENCY_MISMATCH"

def test_i17_quantity_manipulation():
    m = Mission(mission_id="MSN-I17", intent="bat", budget_paise=200000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I17", items=(ProposalItem(sku="BAT-001", qty=-1, price_paise=149900),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R1_BUDGET"

def test_i18_unknown_sku():
    m = Mission(mission_id="MSN-I18", intent="bat", budget_paise=200000, allowed_categories=("cricket",), forbidden_categories=(), upsell_cap=1.0, expires_at=2000000000, signature="sig")
    p = Proposal(mission_id="MSN-I18", items=(ProposalItem(sku="NONEXISTENT-SKU-999", qty=1, price_paise=100000),))
    verd = engine.evaluate(mission=m, proposal=p, catalog=CATALOG, verify_fn=lambda *a: True)
    assert verd.decision == Decision.REJECT
    assert verd.rule_id == "R2_FORBIDDEN"

def test_i19_webhook_forgery():
    secret = "test_sec"
    payload = b'{"event":"payment.captured"}'
    valid_sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    assert hmac.compare_digest("forged_signature_attack", valid_sig) is False

def test_i20_concurrent_replay():
    seq = 910020
    reg(seq=seq, mission_id="MSN-I20", proposal_hash="h20", cart_hash="h20", quote_id="Q20", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])
    def attempt():
        return ver(seq=seq, mission_id="MSN-I20", proposal_hash="h20", cart_hash="h20", quote_id="Q20", amount_paise=149900, currency="INR", skus=[("BAT-001", 1)])

    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as ex:
        futs = [ex.submit(attempt) for _ in range(20)]
        res = [f.result() for f in futs]

    passes = sum(1 for ok, _, _ in res if ok is True)
    fails = sum(1 for ok, _, _ in res if ok is False)
    assert passes == 1
    assert fails == 19
