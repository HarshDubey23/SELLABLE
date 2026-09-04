"""Robust Playwright automation for Razorpay hosted payment-LINK pages.

Day-3 lesson: driving the checkout MODAL broke four times against live DOM.
This drives the payment LINK page instead — a full hosted page with a far
more stable DOM — using layered locator strategies with a screenshot at
every step.

Test-mode credentials (Razorpay published):
  UPI : success@razorpay                  -> deterministic success
  Card: 4111 1111 1111 1111, 12/36, 123   -> deterministic success

HONESTY RULE: this module never declares success on its own. The only sources
of truth for "captured" are the payment.captured webhook or the Razorpay
payments API. If automation fails it raises ManualPaymentNeeded carrying the
URL; the human pays on camera and the caller keeps polling. Never fake it.
"""
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import Page
from playwright.async_api import TimeoutError as PWTimeoutError

SHOT_DIR = Path("docs/log/day05/screenshots")
TEST_UPI_VPA = "success@razorpay"
TEST_CARD = {"number": "4111111111111111", "expiry": "12/36", "cvv": "123"}


class ManualPaymentNeeded(Exception):
    """Automation could not complete; a human must pay at `url` on camera."""

    def __init__(self, url: str, reason: str) -> None:
        super().__init__(f"manual payment needed: {reason}")
        self.url = url
        self.reason = reason


@dataclass
class LinkPaymentResult:
    method: str
    short_url: str
    steps: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)


async def _shot(page: Page, shots: Path, name: str, r: LinkPaymentResult) -> None:
    try:
        p = shots / f"{name}.png"
        await page.screenshot(path=str(p), full_page=True)
        r.screenshots.append(str(p))
        r.steps.append(f"screenshot: {p}")
    except Exception as exc:
        r.steps.append(f"screenshot failed ({name}): {exc}")


async def _click_first(page: Page, selectors: list[str], timeout: int = 3000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            await loc.wait_for(state="visible", timeout=timeout)
            await loc.click(timeout=timeout)
            return True
        except Exception:
            continue
    return False


async def _fill_first(page: Page, selectors: list[str], value: str, timeout: int = 3000) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            await loc.wait_for(state="visible", timeout=timeout)
            await loc.fill(value)
            return True
        except Exception:
            continue
    return False


async def _pay_upi(page: Page, r: LinkPaymentResult, shots: Path) -> None:
    if not await _click_first(page, [
        "text=/pay by upi/i", "text=/^upi$/i", "[data-testid*='upi' i]", "text=/upi/i",
    ]):
        raise ManualPaymentNeeded(page.url, "could not locate a UPI option")
    r.steps.append("selected UPI method")
    await _shot(page, shots, "02_upi_selected", r)
    if not await _fill_first(page, [
        "input[placeholder*='@' i]", "input[name*='vpa' i]", "input[id*='vpa' i]",
        "input[type='text']", "input:not([type])",
    ], TEST_UPI_VPA):
        raise ManualPaymentNeeded(page.url, "could not locate the UPI VPA input")
    r.steps.append(f"entered VPA {TEST_UPI_VPA}")
    await _shot(page, shots, "03_vpa_entered", r)
    if not await _click_first(page, [
        "button:has-text('Pay')", "button:has-text('Verify')",
        "button:has-text('Proceed')", "button[type='submit']", "input[type='submit']",
    ]):
        raise ManualPaymentNeeded(page.url, "could not find the pay/verify button")
    r.steps.append("submitted payment")
    await _shot(page, shots, "04_submitted", r)


async def _pay_card(page: Page, r: LinkPaymentResult, shots: Path) -> None:
    await _click_first(page, ["text=/card/i", "[data-testid*='card' i]"])
    r.steps.append("selected card method (if a tab existed)")
    await _shot(page, shots, "02_card_selected", r)
    fills = [
        (["input[placeholder*='card number' i]", "input[inputmode='numeric']"],
         TEST_CARD["number"], "card number"),
        (["input[name*='exp' i]", "input[placeholder*='mm' i]", "input[placeholder*='expiry' i]"],
         TEST_CARD["expiry"], "expiry"),
        (["input[name*='cvv' i]", "input[placeholder*='cvv' i]"],
         TEST_CARD["cvv"], "cvv"),
    ]
    for sels, val, label in fills:
        if not await _fill_first(page, sels, val):
            raise ManualPaymentNeeded(page.url, f"could not locate the {label} input")
        r.steps.append(f"entered {label}")
    await _shot(page, shots, "03_card_entered", r)
    if not await _click_first(page, ["button:has-text('Pay')", "button[type='submit']"]):
        raise ManualPaymentNeeded(page.url, "could not find the pay button")
    r.steps.append("submitted payment")
    await _shot(page, shots, "04_submitted", r)


async def _wait_success(page: Page, r: LinkPaymentResult) -> None:
    try:
        await page.wait_for_url(re.compile(r"success|paid|status=success", re.I), timeout=45000)
        r.steps.append("reached success URL")
        return
    except PWTimeoutError:
        pass
    try:
        await page.wait_for_selector(
            "text=/(payment )?(success|received|completed|done)/i",
            timeout=30000,
        )
        r.steps.append("success confirmation text visible")
        return
    except PWTimeoutError:
        raise ManualPaymentNeeded(page.url, "no success confirmation within timeout")


async def pay_payment_link(short_url: str, *, headful: bool = False,
                           method: str = "upi") -> LinkPaymentResult:
    """Drive the hosted payment-link page to a test-mode payment.

    Raises ManualPaymentNeeded on automation failure — the caller then
    surfaces the URL for a human payment (on camera) and keeps polling.
    NEVER claims success itself; only the webhook / payments API can.
    """
    from playwright.async_api import async_playwright

    run_id = time.strftime("%Y%m%d_%H%M%S")
    shots = SHOT_DIR / run_id
    shots.mkdir(parents=True, exist_ok=True)
    result = LinkPaymentResult(method=method, short_url=short_url)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=not headful,
                                           slow_mo=500 if headful else 0)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})
        try:
            await page.goto(short_url, wait_until="domcontentloaded", timeout=45000)
            await page.wait_for_load_state("networkidle")
            await _shot(page, shots, "01_link_loaded", result)
            if method == "upi":
                await _pay_upi(page, result, shots)
            else:
                await _pay_card(page, result, shots)
            await _wait_success(page, result)
            await _shot(page, shots, "05_success", result)
        finally:
            await browser.close()
    return result
