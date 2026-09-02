import pytest

from apps.api.gateway_service import GatewayException, GatewayMode, SimulatorGateway
from apps.api.money_types import Money, MoneyError


def test_money_creation_and_formatting():
    m = Money.from_inr(1999)
    assert m.paise == 199900
    assert m.currency == "INR"
    assert m.format_inr() == "Rs 1,999.00"

def test_money_arithmetic():
    m1 = Money.from_inr(100)
    m2 = Money.from_inr(50)
    assert (m1 + m2).to_inr() == 150.0
    assert (m1 - m2).to_inr() == 50.0
    assert (m2 * 3).to_inr() == 150.0

def test_money_negative_forbidden():
    with pytest.raises(MoneyError):
        Money(paise=-100)
    m1 = Money.from_inr(50)
    m2 = Money.from_inr(100)
    with pytest.raises(MoneyError):
        _ = m1 - m2

def test_money_float_forbidden():
    with pytest.raises(MoneyError):
        Money.from_inr(19.99)

def test_simulator_gateway_normal():
    sim = SimulatorGateway(GatewayMode.NORMAL)
    order = sim.create_order(149900, "rcpt_test", {"note": "1"})
    assert order["id"].startswith("order_sim_")
    assert order["amount"] == 149900

def test_simulator_gateway_timeout_fault():
    sim = SimulatorGateway(GatewayMode.CREATE_ORDER_TIMEOUT)
    with pytest.raises(GatewayException) as exc:
        sim.create_order(149900, "rcpt_test", {})
    assert exc.value.code == "GATEWAY_TIMEOUT"
    assert exc.value.status_code == 504

def test_simulator_gateway_rate_limit_fault():
    sim = SimulatorGateway(GatewayMode.GATEWAY_429)
    with pytest.raises(GatewayException) as exc:
        sim.create_order(149900, "rcpt_test", {})
    assert exc.value.code == "RATE_LIMIT_EXCEEDED"
    assert exc.value.status_code == 429
