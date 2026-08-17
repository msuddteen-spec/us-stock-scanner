from __future__ import annotations

from datetime import datetime, timezone

from .models import Fill, OrderRequest, Position


class SimulatedPaperBroker:
    """In-memory long-only broker used by tests and the offline backtester."""

    def __init__(self, starting_cash: float = 100_000.0):
        self.cash = float(starting_cash)
        self.positions: dict[str, Position] = {}
        self.fills: list[Fill] = []
        self._prices: dict[str, float] = {}

    def set_price(self, symbol: str, price: float) -> None:
        self._prices[symbol.upper()] = float(price)

    def submit_order(self, order: OrderRequest, *, fill_price: float | None = None) -> Fill:
        symbol = order.symbol.upper()
        price = float(fill_price or self._prices.get(symbol, 0))
        if price <= 0 or order.quantity <= 0:
            raise ValueError("A positive fill price and quantity are required")
        if order.side.lower() == "buy":
            cost = price * order.quantity
            if cost > self.cash:
                raise ValueError("insufficient simulated cash")
            existing = self.positions.get(symbol)
            if existing:
                total_qty = existing.quantity + order.quantity
                avg = ((existing.quantity * existing.average_price) + cost) / total_qty
                existing.quantity = total_qty
                existing.average_price = avg
            else:
                self.positions[symbol] = Position(symbol, order.quantity, price)
            self.cash -= cost
        elif order.side.lower() == "sell":
            existing = self.positions.get(symbol)
            if not existing or order.quantity > existing.quantity:
                raise ValueError("cannot sell more than the simulated position")
            self.cash += price * order.quantity
            existing.quantity -= order.quantity
            if existing.quantity == 0:
                del self.positions[symbol]
        else:
            raise ValueError("only buy and sell orders are supported")
        fill = Fill(symbol, order.side.lower(), order.quantity, price, datetime.now(timezone.utc))
        self.fills.append(fill)
        return fill

    def equity(self) -> float:
        return self.cash + sum(p.quantity * self._prices.get(symbol, p.average_price) for symbol, p in self.positions.items())


class AlpacaPaperBroker:
    """Alpaca broker adapter with a hard paper-account guard."""

    def __init__(self, settings):
        settings.validate_alpaca_credentials()
        if settings.alpaca_paper is not True:
            raise ValueError("Live Alpaca trading is disabled by design in this MVP")
        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.enums import OrderSide, TimeInForce
            from alpaca.trading.requests import LimitOrderRequest, MarketOrderRequest, StopOrderRequest
        except ImportError as exc:
            raise RuntimeError("Install the optional Alpaca dependency with: pip install -e '.[alpaca]'") from exc
        self._client = TradingClient(settings.alpaca_api_key, settings.alpaca_secret_key, paper=True)
        self._OrderSide = OrderSide
        self._TimeInForce = TimeInForce
        self._MarketOrderRequest = MarketOrderRequest
        self._LimitOrderRequest = LimitOrderRequest
        self._StopOrderRequest = StopOrderRequest

    def account(self):
        return self._client.get_account()

    def positions(self):
        return self._client.get_all_positions()

    def submit_order(self, order: OrderRequest):
        side = self._OrderSide.BUY if order.side.lower() == "buy" else self._OrderSide.SELL
        kwargs = {"symbol": order.symbol.upper(), "qty": order.quantity, "side": side, "time_in_force": self._TimeInForce.DAY}
        if order.order_type == "market":
            request = self._MarketOrderRequest(**kwargs)
        elif order.order_type == "limit" and order.limit_price:
            request = self._LimitOrderRequest(**kwargs, limit_price=order.limit_price)
        elif order.order_type == "stop" and order.stop_price:
            request = self._StopOrderRequest(**kwargs, stop_price=order.stop_price)
        else:
            raise ValueError("Unsupported or incomplete Alpaca order request")
        return self._client.submit_order(request)

    def submit_bracket_order(self, order: OrderRequest, *, stop_loss: float, take_profit: float):
        """Submit an entry with broker-native protective exits in paper mode."""
        try:
            from alpaca.trading.enums import OrderClass
            from alpaca.trading.requests import StopLossRequest, TakeProfitRequest
        except ImportError as exc:
            raise RuntimeError("Alpaca SDK is required for bracket orders") from exc
        if order.side.lower() != "buy" or order.order_type != "market":
            raise ValueError("Bracket entries in this MVP must be long market orders")
        request = self._MarketOrderRequest(
            symbol=order.symbol.upper(),
            qty=order.quantity,
            side=self._OrderSide.BUY,
            time_in_force=self._TimeInForce.DAY,
            order_class=OrderClass.BRACKET,
            take_profit=TakeProfitRequest(limit_price=take_profit),
            stop_loss=StopLossRequest(stop_price=stop_loss),
        )
        return self._client.submit_order(request)

    def cancel_all_open_orders(self):
        return self._client.cancel_orders()
