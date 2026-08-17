from __future__ import annotations

import os
from dataclasses import dataclass


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    alpaca_data_feed: str = "iex"
    symbols: tuple[str, ...] = ("AAPL",)
    timeframe: str = "1Day"
    lookback_bars: int = 120
    risk_per_trade_pct: float = 0.005
    max_position_pct: float = 0.10
    max_daily_loss_pct: float = 0.02
    max_open_positions: int = 5
    starting_cash: float = 100_000.0
    log_path: str = "data/trades.jsonl"
    realtime_refresh_seconds: int = 60

    @classmethod
    def from_env(cls) -> "Settings":
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            # Environment variables still work when the optional loader is absent.
            pass
        symbols = tuple(s.strip().upper() for s in os.getenv("SYMBOLS", "AAPL").split(",") if s.strip())
        settings = cls(
            alpaca_api_key=os.getenv("ALPACA_API_KEY", ""),
            alpaca_secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            alpaca_paper=_bool_env("ALPACA_PAPER", True),
            alpaca_data_feed=os.getenv("ALPACA_DATA_FEED", "iex").lower(),
            symbols=symbols or ("AAPL",),
            timeframe=os.getenv("TIMEFRAME", "1Day"),
            lookback_bars=int(os.getenv("LOOKBACK_BARS", "120")),
            risk_per_trade_pct=float(os.getenv("RISK_PER_TRADE_PCT", "0.005")),
            max_position_pct=float(os.getenv("MAX_POSITION_PCT", "0.10")),
            max_daily_loss_pct=float(os.getenv("MAX_DAILY_LOSS_PCT", "0.02")),
            max_open_positions=int(os.getenv("MAX_OPEN_POSITIONS", "5")),
            starting_cash=float(os.getenv("STARTING_CASH", "100000")),
            log_path=os.getenv("LOG_PATH", "data/trades.jsonl"),
            realtime_refresh_seconds=int(os.getenv("REALTIME_REFRESH_SECONDS", "60")),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        if not self.alpaca_paper:
            raise ValueError("This MVP is paper-only. ALPACA_PAPER must remain true.")
        if not 0 < self.risk_per_trade_pct <= 0.02:
            raise ValueError("RISK_PER_TRADE_PCT must be between 0 and 0.02.")
        if not 0 < self.max_position_pct <= 1:
            raise ValueError("MAX_POSITION_PCT must be between 0 and 1.")
        if not 0 < self.max_daily_loss_pct <= 0.10:
            raise ValueError("MAX_DAILY_LOSS_PCT must be between 0 and 0.10.")
        if self.lookback_bars < 20 or self.max_open_positions < 1:
            raise ValueError("LOOKBACK_BARS must be >= 20 and MAX_OPEN_POSITIONS >= 1.")
        if self.realtime_refresh_seconds < 15:
            raise ValueError("REALTIME_REFRESH_SECONDS must be at least 15 seconds.")

    def validate_alpaca_credentials(self) -> None:
        self.validate()
        if not self.alpaca_api_key or not self.alpaca_secret_key:
            raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY are required for Alpaca paper mode.")
