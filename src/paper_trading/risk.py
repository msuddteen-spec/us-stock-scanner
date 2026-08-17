from __future__ import annotations

from dataclasses import dataclass

from .models import Position


@dataclass(frozen=True)
class RiskDecision:
    approved: bool
    reason: str


class RiskManager:
    def __init__(self, *, max_position_pct: float = 0.10, max_daily_loss_pct: float = 0.02, max_open_positions: int = 5):
        self.max_position_pct = max_position_pct
        self.max_daily_loss_pct = max_daily_loss_pct
        self.max_open_positions = max_open_positions

    def approve_entry(self, symbol: str, quantity: int, price: float, stop_price: float, *, equity: float, positions: dict[str, Position], daily_realized_pnl: float) -> RiskDecision:
        if quantity <= 0:
            return RiskDecision(False, "quantity must be positive")
        if price <= 0 or stop_price <= 0 or stop_price >= price:
            return RiskDecision(False, "stop must be below entry price for long-only MVP")
        if daily_realized_pnl <= -(equity * self.max_daily_loss_pct):
            return RiskDecision(False, "daily loss limit reached; trading halted")
        if symbol in positions:
            return RiskDecision(False, "average-down/re-entry while position is open is disabled")
        if len(positions) >= self.max_open_positions:
            return RiskDecision(False, "maximum number of open positions reached")
        if quantity * price > equity * self.max_position_pct:
            return RiskDecision(False, "position notional exceeds max position percentage")
        return RiskDecision(True, "approved")

    def approve_exit(self, symbol: str, quantity: int, positions: dict[str, Position]) -> RiskDecision:
        position = positions.get(symbol)
        if not position:
            return RiskDecision(False, "cannot sell a symbol with no open position")
        if quantity <= 0 or quantity > position.quantity:
            return RiskDecision(False, "exit quantity exceeds open position")
        return RiskDecision(True, "approved")
