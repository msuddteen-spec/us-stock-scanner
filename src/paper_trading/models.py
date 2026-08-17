from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Bar:
    symbol: str
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class Levels:
    support: float | None
    resistance: float | None
    support_score: float = 0.0
    resistance_score: float = 0.0
    support_zone: tuple[float, float] | None = None
    resistance_zone: tuple[float, float] | None = None


@dataclass(frozen=True)
class Signal:
    symbol: str
    action: SignalAction
    price: float
    stop_loss: float | None
    take_profit: float | None
    score: float
    reason: str
    timestamp: datetime


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: str
    quantity: int
    order_type: str = "market"
    limit_price: float | None = None
    stop_price: float | None = None


@dataclass
class Position:
    symbol: str
    quantity: int
    average_price: float
    stop_loss: float | None = None
    take_profit: float | None = None


@dataclass(frozen=True)
class Fill:
    symbol: str
    side: str
    quantity: int
    price: float
    timestamp: datetime


@dataclass(frozen=True)
class Trade:
    symbol: str
    entry_time: datetime
    exit_time: datetime
    quantity: int
    entry_price: float
    exit_price: float
    pnl: float
    exit_reason: str


@dataclass(frozen=True)
class BacktestResult:
    starting_cash: float
    ending_equity: float
    total_return_pct: float
    trades: tuple[Trade, ...] = field(default_factory=tuple)
    max_drawdown_pct: float = 0.0
    win_rate_pct: float = 0.0
    profit_factor: float = 0.0
