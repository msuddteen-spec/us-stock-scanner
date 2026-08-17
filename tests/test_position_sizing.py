from paper_trading.position_sizing import calculate_position_size


def test_position_size_is_bounded_by_risk_and_notional():
    quantity = calculate_position_size(100_000, 100, 95, risk_per_trade_pct=0.005, max_position_pct=0.10)
    assert quantity == 100


def test_invalid_long_stop_returns_zero():
    assert calculate_position_size(100_000, 100, 101) == 0
