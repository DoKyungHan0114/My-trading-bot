"""
Alpaca broker integration for order execution.
"""
import logging
from datetime import datetime
from typing import Optional

try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

from config.constants import OrderSide, OrderStatus, OrderType
from config.settings import get_settings
from execution.orders import Order

logger = logging.getLogger(__name__)


class AlpacaBroker:
    """Alpaca trading broker for order execution."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
    ):
        """
        Initialize Alpaca broker.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            paper: Use paper trading (default True)
        """
        settings = get_settings()
        self.api_key = api_key or settings.alpaca.api_key
        self.secret_key = secret_key or settings.alpaca.secret_key
        self.paper = paper
        self._client: Optional[TradingClient] = None
        self._order_count = 0

    @property
    def client(self) -> "TradingClient":
        """Lazy initialize trading client."""
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-py not installed")
        if self._client is None:
            self._client = TradingClient(
                api_key=self.api_key,
                secret_key=self.secret_key,
                paper=self.paper,
            )
        return self._client

    @property
    def order_count(self) -> int:
        """Get total orders placed."""
        return self._order_count

    def get_account(self) -> dict:
        """
        Get account information.

        Returns:
            Account details dictionary
        """
        if not ALPACA_AVAILABLE:
            return self._mock_account()

        try:
            account = self.client.get_account()
            return {
                "account_number": account.account_number,
                "status": account.status,
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity),
                "portfolio_value": float(account.portfolio_value),
                "pattern_day_trader": account.pattern_day_trader,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
            }
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            return self._mock_account()

    def _mock_account(self) -> dict:
        """Return mock account for testing."""
        return {
            "account_number": "MOCK",
            "status": "ACTIVE",
            "cash": 10000.0,
            "buying_power": 10000.0,
            "equity": 10000.0,
            "portfolio_value": 10000.0,
            "pattern_day_trader": False,
            "trading_blocked": False,
            "transfers_blocked": False,
        }

    def get_positions(self) -> list[dict]:
        """
        Get all open positions.

        Returns:
            List of position dictionaries
        """
        if not ALPACA_AVAILABLE:
            return []

        try:
            positions = self.client.get_all_positions()
            return [
                {
                    "symbol": p.symbol,
                    "quantity": float(p.qty),
                    "avg_entry_price": float(p.avg_entry_price),
                    "market_value": float(p.market_value),
                    "cost_basis": float(p.cost_basis),
                    "unrealized_pl": float(p.unrealized_pl),
                    "unrealized_plpc": float(p.unrealized_plpc),
                    "current_price": float(p.current_price),
                    "side": p.side,
                }
                for p in positions
            ]
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def get_position(self, symbol: str) -> Optional[dict]:
        """
        Get position for a specific symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position dictionary or None
        """
        if not ALPACA_AVAILABLE:
            return None

        try:
            position = self.client.get_open_position(symbol)
            return {
                "symbol": position.symbol,
                "quantity": float(position.qty),
                "avg_entry_price": float(position.avg_entry_price),
                "market_value": float(position.market_value),
                "cost_basis": float(position.cost_basis),
                "unrealized_pl": float(position.unrealized_pl),
                "unrealized_plpc": float(position.unrealized_plpc),
                "current_price": float(position.current_price),
            }
        except Exception as e:
            logger.debug(f"No position found for {symbol}: {e}")
            return None

    def submit_order(self, order: Order) -> Order:
        """
        Submit order to Alpaca.

        Args:
            order: Order to submit

        Returns:
            Updated order with Alpaca order ID
        """
        if not ALPACA_AVAILABLE:
            return self._mock_submit_order(order)

        try:
            alpaca_side = (
                AlpacaOrderSide.BUY
                if order.side == OrderSide.BUY
                else AlpacaOrderSide.SELL
            )

            if order.order_type == OrderType.MARKET:
                request = MarketOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                request = LimitOrderRequest(
                    symbol=order.symbol,
                    qty=order.quantity,
                    side=alpaca_side,
                    time_in_force=TimeInForce.DAY,
                    limit_price=order.limit_price,
                )

            result = self.client.submit_order(request)
            self._order_count += 1

            order.alpaca_order_id = result.id
            order.status = OrderStatus.PENDING

            if result.filled_at:
                order.fill(
                    price=float(result.filled_avg_price),
                    quantity=float(result.filled_qty),
                    timestamp=result.filled_at,
                )

            logger.info(
                f"Order submitted: {order.side.value} {order.quantity} {order.symbol} "
                f"(Alpaca ID: {order.alpaca_order_id})"
            )

            return order

        except Exception as e:
            logger.error(f"Failed to submit order: {e}")
            order.reject()
            return order

    def _mock_submit_order(self, order: Order) -> Order:
        """Mock order submission for testing."""
        import random

        self._order_count += 1
        order.alpaca_order_id = f"MOCK-{order.order_id[:8]}"

        # Simulate fill with small slippage
        slippage = random.uniform(-0.001, 0.002)
        fill_price = (order.limit_price or 50.0) * (1 + slippage)

        order.fill(
            price=fill_price,
            quantity=order.quantity,
            timestamp=datetime.utcnow(),
        )

        logger.info(f"Mock order filled: {order.to_dict()}")
        return order

    def get_order(self, order_id: str) -> Optional[dict]:
        """
        Get order status.

        Args:
            order_id: Alpaca order ID

        Returns:
            Order details or None
        """
        if not ALPACA_AVAILABLE:
            return None

        try:
            order = self.client.get_order_by_id(order_id)
            return {
                "id": order.id,
                "symbol": order.symbol,
                "side": order.side,
                "qty": float(order.qty),
                "filled_qty": float(order.filled_qty) if order.filled_qty else 0,
                "status": order.status,
                "filled_avg_price": (
                    float(order.filled_avg_price) if order.filled_avg_price else None
                ),
                "created_at": order.created_at,
                "filled_at": order.filled_at,
            }
        except Exception as e:
            logger.error(f"Failed to get order {order_id}: {e}")
            return None

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Alpaca order ID

        Returns:
            True if cancelled successfully
        """
        if not ALPACA_AVAILABLE:
            return True

        try:
            self.client.cancel_order_by_id(order_id)
            logger.info(f"Order cancelled: {order_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel order {order_id}: {e}")
            return False

    def cancel_all_orders(self) -> int:
        """
        Cancel all open orders.

        Returns:
            Number of orders cancelled
        """
        if not ALPACA_AVAILABLE:
            return 0

        try:
            result = self.client.cancel_orders()
            count = len(result) if result else 0
            logger.info(f"Cancelled {count} orders")
            return count
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return 0

    def close_position(self, symbol: str) -> Optional[dict]:
        """
        Close entire position in a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Close order details or None
        """
        if not ALPACA_AVAILABLE:
            return None

        try:
            result = self.client.close_position(symbol)
            self._order_count += 1
            logger.info(f"Position closed: {symbol}")
            return {
                "id": result.id,
                "symbol": result.symbol,
                "qty": float(result.qty),
                "side": result.side,
            }
        except Exception as e:
            logger.error(f"Failed to close position {symbol}: {e}")
            return None

    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        if not ALPACA_AVAILABLE:
            return True  # Assume open for testing

        try:
            clock = self.client.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Failed to check market status: {e}")
            return False
