from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol, Sequence

from .models import Bar


class MarketDataAdapter(Protocol):
    def get_bars(self, symbol: str, *, limit: int = 120) -> list[Bar]: ...

    def get_latest_price(self, symbol: str) -> tuple[float, datetime]: ...


class CsvMarketDataAdapter:
    """Offline adapter for repeatable backtests and local development."""

    def __init__(self, csv_path: str, symbol: str):
        self.csv_path = csv_path
        self.symbol = symbol.upper()

    def get_bars(self, symbol: str | None = None, *, limit: int = 120) -> list[Bar]:
        import pandas as pd

        requested = (symbol or self.symbol).upper()
        frame = pd.read_csv(self.csv_path)
        required = {"timestamp", "open", "high", "low", "close", "volume"}
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"CSV is missing columns: {', '.join(sorted(missing))}")
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        frame = frame.sort_values("timestamp").tail(limit)
        return [
            Bar(requested, row.timestamp.to_pydatetime(), float(row.open), float(row.high), float(row.low), float(row.close), float(row.volume))
            for row in frame.itertuples(index=False)
        ]

    def get_latest_price(self, symbol: str) -> tuple[float, datetime]:
        bars = self.get_bars(symbol, limit=1)
        if not bars:
            raise ValueError("CSV contains no bars")
        return bars[-1].close, bars[-1].timestamp


class AlpacaMarketDataAdapter:
    """Alpaca historical stock data adapter; credentials are never used for live orders."""

    def __init__(self, settings):
        settings.validate_alpaca_credentials()
        try:
            from alpaca.data.enums import DataFeed
            from alpaca.data.historical import StockHistoricalDataClient
            from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest, StockSnapshotRequest
            from alpaca.data.timeframe import TimeFrame
        except ImportError as exc:
            raise RuntimeError("Install the optional Alpaca dependency with: pip install -e '.[alpaca]'") from exc
        self._client = StockHistoricalDataClient(settings.alpaca_api_key, settings.alpaca_secret_key)
        self._request_type = StockBarsRequest
        self._latest_trade_request = StockLatestTradeRequest
        self._snapshot_request = StockSnapshotRequest
        self._timeframe = TimeFrame.Day if settings.timeframe == "1Day" else TimeFrame.Hour
        self._feed = DataFeed.IEX if settings.alpaca_data_feed == "iex" else DataFeed.SIP

    def get_bars(self, symbol: str, *, limit: int = 120) -> list[Bar]:
        return self.get_bars_for_symbols([symbol], limit=limit).get(symbol.upper(), [])

    def get_bars_for_symbols(self, symbols: Sequence[str], *, limit: int = 120, batch_size: int = 50) -> dict[str, list[Bar]]:
        """Fetch the most-recent completed bars for a batch of symbols."""
        end = datetime.now(timezone.utc)
        # Give Alpaca a broad calendar window so holidays/weekends still yield
        # enough completed bars for swing-level calculations. Do not pass the
        # requested limit to Alpaca: that API returns the *first* bars in the
        # range, which would make support/resistance stale. We take the latest
        # bars after sorting instead.
        start = end - timedelta(days=max(365, limit * 3))
        requested = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        result: dict[str, list[Bar]] = {symbol: [] for symbol in requested}
        for batch in _chunks(requested, batch_size):
            request = self._request_type(symbol_or_symbols=list(batch), timeframe=self._timeframe, start=start, end=end, feed=self._feed)
            frame = self._client.get_stock_bars(request).df.reset_index()
            if frame.empty:
                continue
            for row in frame.sort_values("timestamp").itertuples(index=False):
                symbol = str(row.symbol).upper()
                if symbol in result:
                    result[symbol].append(Bar(symbol, _as_datetime(row.timestamp), float(row.open), float(row.high), float(row.low), float(row.close), float(row.volume)))
        return {symbol: bars[-limit:] for symbol, bars in result.items()}

    def get_latest_price(self, symbol: str) -> tuple[float, datetime]:
        return self.get_latest_prices([symbol])[symbol.upper()]

    def get_latest_prices(self, symbols: Sequence[str], *, batch_size: int = 2_000) -> dict[str, tuple[float, datetime]]:
        result: dict[str, tuple[float, datetime]] = {}
        requested = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        for batch in _chunks(requested, batch_size):
            trades = self._client.get_stock_latest_trade(self._latest_trade_request(symbol_or_symbols=list(batch), feed=self._feed))
            for symbol, trade in trades.items():
                result[symbol.upper()] = (float(trade.price), _as_datetime(trade.timestamp))
        return result

    def most_liquid_symbols(self, symbols: Sequence[str], *, limit: int = 50, batch_size: int = 2_000) -> list[str]:
        """Screen every supplied symbol by the latest daily dollar volume."""
        candidates: list[tuple[float, float, str]] = []
        requested = tuple(dict.fromkeys(symbol.upper() for symbol in symbols))
        for batch in _chunks(requested, batch_size):
            snapshots = self._client.get_stock_snapshot(self._snapshot_request(symbol_or_symbols=list(batch), feed=self._feed))
            for symbol, snapshot in snapshots.items():
                bar = snapshot.daily_bar
                previous = snapshot.previous_daily_bar
                if not bar or bar.close is None or bar.volume is None:
                    continue
                price = float(bar.close)
                dollar_volume = price * float(bar.volume)
                if not 5 <= price <= 2_000 or dollar_volume < 1_000_000:
                    continue
                change_pct = 0.0
                if previous and previous.close:
                    change_pct = (price - float(previous.close)) / float(previous.close)
                candidates.append((dollar_volume, change_pct, symbol.upper()))
        candidates.sort(reverse=True)
        return [symbol for _, _, symbol in candidates[:limit]]


def _as_datetime(value) -> datetime:
    if hasattr(value, "to_pydatetime"):
        return value.to_pydatetime()
    return value


def _chunks(values: Sequence[str], size: int):
    for start in range(0, len(values), size):
        yield values[start : start + size]
