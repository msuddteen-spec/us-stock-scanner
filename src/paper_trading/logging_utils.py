from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path

from .models import Signal, Trade


def configure_logging(level: str = "INFO") -> None:
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")


class TradeLogger:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def log_signal(self, signal: Signal) -> None:
        self._append({"event": "signal", **_jsonable(asdict(signal))})

    def log_trade(self, trade: Trade) -> None:
        self._append({"event": "trade", **_jsonable(asdict(trade))})

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def summary(self) -> dict[str, float]:
        trades = [row for row in self.read() if row.get("event") == "trade"]
        pnls = [float(row["pnl"]) for row in trades]
        return {
            "trades": float(len(pnls)),
            "net_pnl": sum(pnls),
            "win_rate_pct": (sum(p > 0 for p in pnls) / len(pnls) * 100) if pnls else 0.0,
            "profit_factor": (sum(p for p in pnls if p > 0) / abs(sum(p for p in pnls if p < 0))) if any(p < 0 for p in pnls) else 0.0,
        }

    def _append(self, event: dict) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, default=str) + "\n")


def _jsonable(value):
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "value"):
        return value.value
    return value
