from __future__ import annotations

import argparse
import json

from .backtest import SwingBacktester
from .config import Settings
from .dashboard import run_dashboard
from .market_data import CsvMarketDataAdapter
from .market_data import AlpacaMarketDataAdapter
from .broker import AlpacaPaperBroker
from .paper_engine import PaperTradingEngine


def main() -> None:
    parser = argparse.ArgumentParser(description="US swing-trading paper MVP")
    sub = parser.add_subparsers(dest="command", required=True)
    backtest = sub.add_parser("backtest", help="Run an offline CSV backtest")
    backtest.add_argument("--csv", required=True)
    backtest.add_argument("--symbol", default="AAPL")
    backtest.add_argument("--cash", type=float, default=100_000)
    dashboard = sub.add_parser("dashboard", help="Open the Streamlit trade log dashboard")
    dashboard.add_argument("--log", default="data/trades.jsonl")
    sub.add_parser("check-config", help="Validate environment settings without connecting")
    scan = sub.add_parser("paper-scan", help="Scan Alpaca data in paper mode; optionally submit a bracket order")
    scan.add_argument("--symbol", default=None)
    scan.add_argument("--execute", action="store_true", help="Submit only to the guarded Alpaca paper account")
    args = parser.parse_args()
    if args.command == "check-config":
        settings = Settings.from_env()
        print(json.dumps({"paper": settings.alpaca_paper, "symbols": settings.symbols, "timeframe": settings.timeframe}, default=str))
    elif args.command == "backtest":
        bars = CsvMarketDataAdapter(args.csv, args.symbol).get_bars(limit=10_000)
        result = SwingBacktester(starting_cash=args.cash).run(bars)
        print(json.dumps({"starting_cash": result.starting_cash, "ending_equity": result.ending_equity, "return_pct": result.total_return_pct, "trades": len(result.trades), "max_drawdown_pct": result.max_drawdown_pct, "win_rate_pct": result.win_rate_pct, "profit_factor": result.profit_factor}, indent=2))
    elif args.command == "dashboard":
        run_dashboard(args.log)
    elif args.command == "paper-scan":
        settings = Settings.from_env()
        data = AlpacaMarketDataAdapter(settings)
        broker = AlpacaPaperBroker(settings)
        engine = PaperTradingEngine(settings, data, broker)
        symbols = (args.symbol.upper(),) if args.symbol else settings.symbols
        for symbol in symbols:
            print(json.dumps(engine.scan(symbol, execute=args.execute), default=str))


if __name__ == "__main__":
    main()
