import pytest

from paper_trading.broker import SimulatedPaperBroker
from paper_trading.models import OrderRequest


def test_simulated_broker_buy_and_sell():
    broker = SimulatedPaperBroker(1_000)
    broker.set_price("TEST", 10)
    broker.submit_order(OrderRequest("TEST", "buy", 50))
    assert broker.cash == 500
    broker.set_price("TEST", 12)
    broker.submit_order(OrderRequest("TEST", "sell", 50))
    assert broker.cash == 1_100
    assert broker.positions == {}


def test_simulated_broker_rejects_overspend():
    broker = SimulatedPaperBroker(100)
    with pytest.raises(ValueError, match="insufficient"):
        broker.submit_order(OrderRequest("TEST", "buy", 11), fill_price=10)
