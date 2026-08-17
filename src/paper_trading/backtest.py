from __future__ import annotations

from dataclasses import replace

from .models import BacktestResult, Bar, OrderRequest, Position, SignalAction, Trade
from .position_sizing import calculate_position_size
from .risk import RiskManager
from .signal import SignalEngine
from .support_resistance import SupportResistanceEngine


class SwingBacktester:
    def __init__(self, *, starting_cash: float = 100_000.0, lookback: int = 60, risk_per_trade_pct: float = 0.005, max_position_pct: float = 0.10):
        self.starting_cash = starting_cash
        self.lookback = lookback
        self.risk_per_trade_pct = risk_per_trade_pct
        self.max_position_pct = max_position_pct
        self.levels = SupportResistanceEngine(lookback=lookback)
        self.signals = SignalEngine()
        self.risk = RiskManager(max_position_pct=max_position_pct)

    def run(self, bars: list[Bar]) -> BacktestResult:
        if len(bars) < self.lookback + 5:
            raise ValueError(f"Need at least {self.lookback + 5} bars")
        cash = self.starting_cash
        position: Position | None = None
        trades: list[Trade] = []
        equity_curve = [cash]
        pending_entry = None
        for index in range(self.lookback, len(bars)):
            bar = bars[index]
            # Execute decisions on the next bar's open to avoid same-bar look-ahead.
            if pending_entry and position is None:
                entry_price, stop, target, signal_time = pending_entry
                quantity = calculate_position_size(cash, entry_price, stop, risk_per_trade_pct=self.risk_per_trade_pct, max_position_pct=self.max_position_pct)
                if quantity:
                    decision = self.risk.approve_entry(bar.symbol, quantity, entry_price, stop, equity=cash, positions={}, daily_realized_pnl=0)
                    if decision.approved and quantity * entry_price <= cash:
                        cash -= quantity * entry_price
                        position = Position(bar.symbol, quantity, entry_price, stop, target)
                pending_entry = None

            if position:
                exit_price = None
                reason = ""
                if bar.low <= (position.stop_loss or 0):
                    exit_price, reason = position.stop_loss, "stop-loss"
                elif bar.high >= (position.take_profit or float("inf")):
                    exit_price, reason = position.take_profit, "take-profit"
                if exit_price:
                    cash += position.quantity * exit_price
                    trades.append(Trade(position.symbol, bars[index - 1].timestamp, bar.timestamp, position.quantity, position.average_price, exit_price, (exit_price - position.average_price) * position.quantity, reason))
                    position = None
            history = bars[: index + 1]
            levels = self.levels.calculate(history)
            signal = self.signals.generate(history, levels, position)
            if position is None and signal.action == SignalAction.BUY and signal.stop_loss and signal.take_profit:
                pending_entry = (bar.open, signal.stop_loss, signal.take_profit, signal.timestamp)
            mark = cash + (position.quantity * bar.close if position else 0)
            equity_curve.append(mark)
        if position:
            final = bars[-1]
            cash += position.quantity * final.close
            trades.append(Trade(position.symbol, bars[-2].timestamp, final.timestamp, position.quantity, position.average_price, final.close, (final.close - position.average_price) * position.quantity, "end-of-test"))
            position = None
        ending = cash
        gross_profit = sum(t.pnl for t in trades if t.pnl > 0)
        gross_loss = abs(sum(t.pnl for t in trades if t.pnl < 0))
        peaks, drawdowns = equity_curve[0], []
        for value in equity_curve:
            peaks = max(peaks, value)
            drawdowns.append((peaks - value) / peaks * 100 if peaks else 0)
        return BacktestResult(self.starting_cash, ending, (ending / self.starting_cash - 1) * 100, tuple(trades), max(drawdowns, default=0), sum(t.pnl > 0 for t in trades) / len(trades) * 100 if trades else 0, gross_profit / gross_loss if gross_loss else float("inf") if gross_profit else 0)
