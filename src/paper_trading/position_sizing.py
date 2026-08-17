from __future__ import annotations

import math


def calculate_position_size(
    equity: float,
    entry_price: float,
    stop_price: float,
    *,
    risk_per_trade_pct: float = 0.005,
    max_position_pct: float = 0.10,
    lot_size: int = 1,
) -> int:
    """Return a whole-share quantity bounded by risk and notional limits."""
    if equity <= 0 or entry_price <= 0 or stop_price <= 0 or entry_price <= stop_price:
        return 0
    if lot_size < 1:
        raise ValueError("lot_size must be >= 1")
    risk_per_share = entry_price - stop_price
    risk_budget = equity * risk_per_trade_pct
    max_notional = equity * max_position_pct
    raw_quantity = min(risk_budget / risk_per_share, max_notional / entry_price)
    return max(0, math.floor(raw_quantity / lot_size) * lot_size)
