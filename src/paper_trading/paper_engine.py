from __future__ import annotations

import logging
from datetime import timedelta, timezone

from .logging_utils import TradeLogger
from .models import Bar, Levels, OrderRequest, Position, SignalAction
from .position_sizing import calculate_position_size
from .risk import RiskManager
from .signal import SignalEngine
from .support_resistance import SupportResistanceEngine

logger = logging.getLogger(__name__)


class PaperTradingEngine:
    """One-shot scanner/executor for an Alpaca paper account.

    Scheduling is intentionally left to an external task runner. Running one
    iteration at a time makes the first version easier to audit and stop.
    """

    def __init__(self, settings, market_data, broker, trade_logger: TradeLogger | None = None):
        self.settings = settings
        self.market_data = market_data
        self.broker = broker
        self.trade_logger = trade_logger or TradeLogger(settings.log_path)
        self.levels_engine = SupportResistanceEngine()
        self.signal_engine = SignalEngine()
        self.risk = RiskManager(max_position_pct=settings.max_position_pct, max_daily_loss_pct=settings.max_daily_loss_pct, max_open_positions=settings.max_open_positions)

    def scan(self, symbol: str, *, execute: bool = False) -> dict:
        bars = self.market_data.get_bars(symbol, limit=self.settings.lookback_bars)
        levels = self.levels_engine.calculate(bars)
        positions = self._positions_as_dict()
        signal = self.signal_engine.generate(bars, levels, positions.get(symbol.upper()))
        self.trade_logger.log_signal(signal)
        result = {"symbol": symbol.upper(), "action": signal.action.value, "price": signal.price, "score": signal.score, "reason": signal.reason, "support": levels.support, "resistance": levels.resistance, "executed": False}
        if execute and signal.action == SignalAction.BUY and signal.stop_loss and signal.take_profit:
            account = self.broker.account()
            equity = float(account.equity)
            quantity = calculate_position_size(equity, signal.price, signal.stop_loss, risk_per_trade_pct=self.settings.risk_per_trade_pct, max_position_pct=self.settings.max_position_pct)
            decision = self.risk.approve_entry(symbol.upper(), quantity, signal.price, signal.stop_loss, equity=equity, positions=positions, daily_realized_pnl=0.0)
            if not decision.approved:
                result["risk_rejection"] = decision.reason
            else:
                order = OrderRequest(symbol.upper(), "buy", quantity)
                self.broker.submit_bracket_order(order, stop_loss=signal.stop_loss, take_profit=signal.take_profit)
                result["executed"] = True
        return result

    def scan_realtime(self, symbol: str, *, record_signal: bool = False) -> dict:
        """Poll the latest trade and evaluate it against completed-bar levels.

        This is deliberately polling-based, not HFT. Levels come from the
        historical swing window while the displayed price/signal uses the
        latest Alpaca trade.
        """
        bars = self.market_data.get_bars(symbol, limit=self.settings.lookback_bars)
        latest_price, latest_timestamp = self.market_data.get_latest_price(symbol)
        return self._evaluate_realtime(symbol, bars, latest_price, latest_timestamp, self._positions_as_dict(), record_signal)

    def scan_many_realtime(self, symbols: list[str] | tuple[str, ...], *, record_signal: bool = False) -> list[dict]:
        """Evaluate many symbols efficiently using batched market-data requests."""
        requested = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        bars_by_symbol = self.market_data.get_bars_for_symbols(requested, limit=self.settings.lookback_bars)
        prices_by_symbol = self.market_data.get_latest_prices(requested)
        positions = self._positions_as_dict()
        results = []
        for symbol in requested:
            bars = bars_by_symbol.get(symbol, [])
            latest = prices_by_symbol.get(symbol)
            if bars and latest:
                results.append(self._evaluate_realtime(symbol, bars, latest[0], latest[1], positions, record_signal))
        return results

    def _evaluate_realtime(self, symbol: str, bars: list[Bar], latest_price: float, latest_timestamp, positions: dict[str, Position], record_signal: bool) -> dict:
        live_bar = Bar(symbol.upper(), latest_timestamp, latest_price, latest_price, latest_price, latest_price, 0.0)
        levels = self.levels_engine.calculate(bars)
        history_timestamp = bars[-1].timestamp
        levels_status = "current"
        if _historical_bars_are_stale(history_timestamp, latest_timestamp):
            # A live quote paired with months-old daily bars produces misleading
            # levels. Hide them until the historical feed is current again.
            levels = Levels(None, None)
            levels_status = "stale"
        signal = self.signal_engine.generate([*bars, live_bar], levels, positions.get(symbol.upper()))
        if record_signal:
            self.trade_logger.log_signal(signal)
        reason = signal.reason
        if levels_status == "stale":
            reason = "historical price bars are stale; support/resistance hidden"
        suggested_base_zone = _suggested_base_zone(latest_price, levels.support)
        return {
            "symbol": symbol.upper(),
            "action": signal.action.value,
            "price": latest_price,
            "timestamp": latest_timestamp,
            "history_timestamp": history_timestamp,
            "levels_status": levels_status,
            "score": signal.score,
            "reason": reason,
            "support": levels.support,
            "resistance": levels.resistance,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "suggested_base_zone": suggested_base_zone,
            "executed": False,
            "data_mode": "real-time poll",
        }

    def _positions_as_dict(self) -> dict[str, Position]:
        raw_positions = self.broker.positions()
        normalized = {}
        for raw in raw_positions:
            symbol = (str(raw.get("symbol")) if isinstance(raw, dict) else str(raw.symbol)).upper()
            quantity = int(float(raw.get("qty", 0))) if isinstance(raw, dict) else int(float(raw.qty))
            average = float(raw.get("avg_entry_price", 0)) if isinstance(raw, dict) else float(raw.avg_entry_price)
            normalized[symbol] = Position(symbol, quantity, average)
        return normalized


def _historical_bars_are_stale(history_timestamp, latest_timestamp, max_age_days: int = 7) -> bool:
    """Return true when completed bars cannot safely support a live quote."""
    if history_timestamp.tzinfo is None:
        history_timestamp = history_timestamp.replace(tzinfo=timezone.utc)
    if latest_timestamp.tzinfo is None:
        latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
    return latest_timestamp - history_timestamp > timedelta(days=max_age_days)


def _suggested_base_zone(price: float, support: float | None, max_support_distance_pct: float = 0.08) -> tuple[float, float] | None:
    """Suggest a nearby consolidation zone only when the major support is too far away."""
    if support is None or price <= 0:
        return None
    support_distance = (price - support) / price
    if support_distance <= max_support_distance_pct:
        return None
    return round(price * 0.95, 2), round(price * 0.98, 2)
