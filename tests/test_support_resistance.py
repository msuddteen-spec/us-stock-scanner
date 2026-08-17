from datetime import datetime, timedelta, timezone

from paper_trading.models import Bar
from paper_trading.paper_engine import _historical_bars_are_stale, _suggested_base_zone
from paper_trading.support_resistance import SupportResistanceEngine


def _bars():
    closes = [100, 103, 106, 103, 100, 103, 106, 103, 100, 103, 106, 104]
    result = []
    for index, close in enumerate(closes):
        result.append(Bar("TEST", datetime(2025, 1, 1, tzinfo=timezone.utc) + timedelta(days=index), close - 1, close + 1, close - 2, close, 1000))
    return result


def test_engine_finds_clustered_levels():
    levels = SupportResistanceEngine(lookback=20, min_touches=2).calculate(_bars())
    assert levels.support is not None
    assert levels.resistance is not None
    assert levels.support < levels.resistance


def test_stale_history_is_not_used_for_live_levels():
    history_time = datetime(2026, 2, 6, tzinfo=timezone.utc)
    assert _historical_bars_are_stale(history_time, history_time + timedelta(days=8))
    assert not _historical_bars_are_stale(history_time, history_time + timedelta(days=3))


def test_suggested_base_zone_only_appears_when_major_support_is_far_away():
    assert _suggested_base_zone(100, 75) == (95.0, 98.0)
    assert _suggested_base_zone(100, 95) is None
