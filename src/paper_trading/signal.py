from __future__ import annotations

from .models import Bar, Levels, Position, Signal, SignalAction


class SignalEngine:
    """Long-only swing rules: support bounce, resistance breakout, and exits."""

    def __init__(self, min_risk_reward: float = 1.5, entry_zone_pct: float = 0.01, breakout_volume_multiple: float = 1.5, max_support_distance_pct: float = 0.08):
        self.min_risk_reward = min_risk_reward
        self.entry_zone_pct = entry_zone_pct
        self.breakout_volume_multiple = breakout_volume_multiple
        self.max_support_distance_pct = max_support_distance_pct

    def generate(self, bars: list[Bar], levels: Levels, position: Position | None = None) -> Signal:
        if not bars:
            raise ValueError("At least one bar is required")
        latest = bars[-1]
        if position:
            if position.stop_loss and latest.close <= position.stop_loss:
                return self._signal(latest, SignalAction.SELL, None, "close reached stop-loss", 100.0)
            if position.take_profit and latest.close >= position.take_profit:
                return self._signal(latest, SignalAction.SELL, None, "close reached take-profit/resistance", 90.0)
            return self._signal(latest, SignalAction.HOLD, None, "position is open; no exit condition", 0.0)
        if levels.support is None or levels.resistance is None:
            return self._signal(latest, SignalAction.HOLD, None, "insufficient support/resistance levels", 0.0)

        support_near = latest.low <= levels.support * (1 + self.entry_zone_pct) and latest.close >= levels.support
        bullish = latest.close > latest.open
        stop = levels.support * (1 - self.entry_zone_pct)
        target = levels.resistance
        reward = target - latest.close
        risk = latest.close - stop
        if support_near and bullish and risk > 0 and reward / risk >= self.min_risk_reward:
            return self._signal(latest, SignalAction.BUY, (stop, target), "bullish bounce near clustered support", min(100.0, 60 + levels.support_score * 0.25))

        average_volume = sum(b.volume for b in bars[-21:-1]) / max(1, len(bars[-21:-1]))
        breakout = latest.close > levels.resistance * (1 + 0.001)
        volume_confirmed = average_volume == 0 or latest.volume >= average_volume * self.breakout_volume_multiple
        if breakout and volume_confirmed:
            breakout_stop = levels.resistance * (1 - self.entry_zone_pct)
            breakout_risk = latest.close - breakout_stop
            breakout_target = latest.close + breakout_risk * self.min_risk_reward
            return self._signal(latest, SignalAction.BUY, (breakout_stop, breakout_target), "resistance breakout with volume confirmation", min(100.0, 65 + levels.resistance_score * 0.25))

        support_distance_pct = max(0.0, (latest.close - levels.support) / latest.close)
        if support_distance_pct > self.max_support_distance_pct:
            return self._signal(latest, SignalAction.HOLD, None, f"support is {support_distance_pct:.1%} below current price; wait for a new base", 0.0)
        return self._signal(latest, SignalAction.HOLD, None, "no qualified swing setup", 0.0)

    def _signal(self, bar: Bar, action: SignalAction, targets, reason: str, score: float) -> Signal:
        stop, target = targets if targets else (None, None)
        return Signal(bar.symbol, action, bar.close, stop, target, round(score, 2), reason, bar.timestamp)
