from __future__ import annotations

from collections import defaultdict

from .models import Bar, Levels


class SupportResistanceEngine:
    """Finds price zones from clustered swing highs/lows.

    This is deliberately deterministic. An LLM may explain the output later, but it
    should not be the component inventing executable price levels.
    """

    def __init__(self, lookback: int = 60, tolerance_pct: float = 0.0075, min_touches: int = 2):
        self.lookback = lookback
        self.tolerance_pct = tolerance_pct
        self.min_touches = min_touches

    def calculate(self, bars: list[Bar]) -> Levels:
        if len(bars) < 5:
            return Levels(None, None)
        recent = bars[-self.lookback :]
        highs, lows = [], []
        for i in range(2, len(recent) - 2):
            window = recent[i - 2 : i + 3]
            if recent[i].high >= max(b.high for b in window):
                highs.append((recent[i].high, recent[i].volume))
            if recent[i].low <= min(b.low for b in window):
                lows.append((recent[i].low, recent[i].volume))
        current = recent[-1].close
        support = self._best_cluster(lows, current, direction="support")
        resistance = self._best_cluster(highs, current, direction="resistance")
        if support is None:
            support = min(b.low for b in recent if b.low <= current) if any(b.low <= current for b in recent) else min(b.low for b in recent)
        if resistance is None:
            resistance = max(b.high for b in recent if b.high >= current) if any(b.high >= current for b in recent) else max(b.high for b in recent)
        return Levels(
            support=support[0] if isinstance(support, tuple) else support,
            resistance=resistance[0] if isinstance(resistance, tuple) else resistance,
            support_score=support[1] if isinstance(support, tuple) else 1.0,
            resistance_score=resistance[1] if isinstance(resistance, tuple) else 1.0,
            support_zone=self._zone(support[0] if isinstance(support, tuple) else support),
            resistance_zone=self._zone(resistance[0] if isinstance(resistance, tuple) else resistance),
        )

    def _best_cluster(self, points, current: float, direction: str):
        candidates = [p for p in points if (p[0] <= current if direction == "support" else p[0] >= current)]
        clusters: list[list[tuple[float, float]]] = []
        for point in sorted(candidates):
            placed = False
            for cluster in clusters:
                center = sum(p[0] for p in cluster) / len(cluster)
                if abs(point[0] - center) / center <= self.tolerance_pct:
                    cluster.append(point)
                    placed = True
                    break
            if not placed:
                clusters.append([point])
        valid = [c for c in clusters if len(c) >= self.min_touches]
        if not valid:
            return None
        # Prefer nearby levels, then levels with more touches.
        valid.sort(key=lambda c: (abs(sum(p[0] for p in c) / len(c) - current), -len(c)))
        cluster = valid[0]
        price = sum(p[0] for p in cluster) / len(cluster)
        score = min(100.0, 45.0 + len(cluster) * 15.0)
        return price, score

    def _zone(self, price: float | None) -> tuple[float, float] | None:
        if price is None:
            return None
        return price * (1 - self.tolerance_pct), price * (1 + self.tolerance_pct)
