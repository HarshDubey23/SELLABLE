"""
Playwright E2E tests for Phase 76.
Run with: pytest tests/e2e/test_ui.py
"""
import pytest
from playwright.sync_api import Page, expect

@pytest.mark.skip(reason="Requires live server and playwright browsers installed")
def test_home_page_loads(page: Page):
    """Test 1: Open home."""
    page.goto("http://localhost:8000/")
    expect(page).to_have_title("SELLABLE")
    expect(page.locator("text=SELLABLE")).to_be_visible()

@pytest.mark.skip(reason="Requires live server and playwright browsers installed")
def test_run_live_mission(page: Page):
    """Test 3: Run mission, observe search, agent trace, gateway, approval."""
    page.goto("http://localhost:8000/mission")
    page.click("button:has-text('Run Mission')")
    
    # Observe search
    expect(page.locator(".evt.system:has-text('SEARCH_PRODUCTS')")).to_be_visible(timeout=10000)
    
    # Observe agent
    expect(page.locator(".evt.buyer:has-text('GET_PRODUCT')")).to_be_visible(timeout=10000)
    
    # Observe gateway
    expect(page.locator(".evt.gateway:has-text('APPROVE')")).to_be_visible(timeout=10000)

@pytest.mark.skip(reason="Requires live server and playwright browsers installed")
def test_attack_lab_blocks(page: Page):
    """Test 14: Attack lab."""
    page.goto("http://localhost:8000/attack-ui")
    page.click("button:has-text('Run All Attacks')")
    
    # Money calls = 0
    expect(page.locator("text=NO Razorpay call")).to_be_visible(timeout=15000)
    expect(page.locator("text=boundary_calls: 0")).to_be_visible()

@pytest.mark.skip(reason="Requires live server and playwright browsers installed")
def test_audit_verification(page: Page):
    """Test 13: Audit verification."""
    page.goto("http://localhost:8000/audit-ui")
    expect(page.locator("text=CHAIN VALID")).to_be_visible(timeout=10000)
