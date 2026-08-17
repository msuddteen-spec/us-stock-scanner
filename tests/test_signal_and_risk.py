from datetime import datetime, timezone

from paper_trading.models import Bar, Levels, Position, SignalAction
from paper_trading.risk import RiskManager
from paper_trading.signal import SignalEngine


def test_support_bounce_generates_buy_signal():
    bars = [Bar("TEST", datetime(2025, 1, 1, tzinfo=timezone.utc), 101, 103, 99, 102, 1000)]
    signal = SignalEngine().generate(bars, Levels(100, 110, 80, 70))
    assert signal.action == SignalAction.BUY
    assert signal.stop_loss < signal.price < signal.take_profit


def test_distant_support_explains_why_to_wait():
    bars = [Bar("TEST", datetime(2025, 1, 1, tzinfo=timezone.utc), 100, 101, 99, 100, 1000)]
    signal = SignalEngine().generate(bars, Levels(75, 120, 80, 70))
    assert signal.action == SignalAction.HOLD
    assert signal.reason == "support is 25.0% below current price; wait for a new base"


def test_risk_manager_blocks_average_down_and_daily_loss():
    manager = RiskManager(max_daily_loss_pct=0.02)
    position = {"TEST": Position("TEST", 10, 100)}
    assert not manager.approve_entry("TEST", 1, 100, 95, equity=10_000, positions=position, daily_realized_pnl=0).approved
    assert not manager.approve_entry("NEW", 1, 100, 95, equity=10_000, positions={}, daily_realized_pnl=-201).approved
