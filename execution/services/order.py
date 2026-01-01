"""
Order service for order submission and management.

Handles order lifecycle: submit, fill, cancel.
"""
import logging
import time
import random
from datetime import datetime
from typing import Optional, Dict, Any

from execution.orders import Order
from execution.services.retry import RetryService, RetryConfig
from config.constants import OrderSide, OrderStatus, OrderType

logger = logging.getLogger(__name__)

# Try to import Alpaca
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest
    from alpaca.trading.enums import OrderSide as AlpacaOrderSide, TimeInForce
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    TradingClient = None
    AlpacaOrderSide = None


class OrderService:
    """
    Service for order submission and management.

    Uses RetryService for robust order execution.
    """

    def __init__(
        self,
        client: Optional["TradingClient"] = None,
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        Initialize order service.

        Args:
            client: Alpaca TradingClient
            retry_config: Retry configuration
        """
        self._client = client
        self._retry_service = RetryService(retry_config or RetryConfig())
        self._order_count = 0

    @property
    def client(self) -> Optional["TradingClient"]:
        return self._client

    @client.setter
    def client(self, value: "TradingClient") -> None:
        self._client = value

    @property
    def order_count(self) -> int:
        """Get total orders placed."""
        return self._order_count

    def submit_order(self, order: Order) -> Order:
        """
        Submit order with retry logic.

        Args:
            order: Order to submit

        Returns:
            Updated order with Alpaca order ID
        """
        if not ALPACA_AVAILABLE or not self._client:
            return self._mock_submit_order(order)

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

        def submit():
            result = self._client.submit_order(request)
            return result

        def on_failure(e: Exception) -> None:
            order.reject()
            return None

        try:
            result = self._retry_service.execute_with_retry(
                operation=submit,
                operation_name=f"submit_order({order.symbol})",
                on_failure=on_failure,
            )

            if result is None:
                return order

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
            logger.error(f"Order submission failed: {e}")
            order.reject()
            return order

    def _mock_submit_order(self, order: Order) -> Order:
        """Mock order submission for testing."""
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

    def get_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """
        Get order status.

        Args:
            order_id: Alpaca order ID

        Returns:
            Order details or None
        """
        if not ALPACA_AVAILABLE or not self._client:
            return None

        try:
            order = self._client.get_order_by_id(order_id)
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
        if not ALPACA_AVAILABLE or not self._client:
            return True

        try:
            self._client.cancel_order_by_id(order_id)
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
        if not ALPACA_AVAILABLE or not self._client:
            return 0

        try:
            result = self._client.cancel_orders()
            count = len(result) if result else 0
            logger.info(f"Cancelled {count} orders")
            return count
        except Exception as e:
            logger.error(f"Failed to cancel all orders: {e}")
            return 0

    def close_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Close entire position in a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Close order details or None
        """
        if not ALPACA_AVAILABLE or not self._client:
            return None

        try:
            result = self._client.close_position(symbol)
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

    def wait_for_fill(
        self,
        order: Order,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
        cancel_on_timeout: bool = True,
    ) -> Order:
        """
        Wait for an order to be filled.

        Args:
            order: Order to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks
            cancel_on_timeout: Cancel unfilled orders on timeout

        Returns:
            Updated order with fill status
        """
        if not ALPACA_AVAILABLE or not self._client or not order.alpaca_order_id:
            return order

        start_time = time.time()
        last_filled_qty = 0.0

        while time.time() - start_time < timeout:
            try:
                alpaca_order = self._client.get_order_by_id(order.alpaca_order_id)
                status = str(alpaca_order.status).lower()
                filled_qty = float(alpaca_order.filled_qty) if alpaca_order.filled_qty else 0

                if status == "filled":
                    order.fill(
                        price=float(alpaca_order.filled_avg_price),
                        quantity=float(alpaca_order.filled_qty),
                        timestamp=alpaca_order.filled_at,
                    )
                    logger.info(
                        f"Order filled: {order.side.value} {order.filled_quantity} {order.symbol} "
                        f"@ ${order.fill_price:.2f}"
                    )
                    return order

                elif status == "cancelled":
                    order.cancel()
                    logger.warning(f"Order was cancelled: {order.alpaca_order_id}")
                    return order

                elif status == "rejected":
                    order.reject()
                    logger.error(f"Order was rejected: {order.alpaca_order_id}")
                    return order

                elif status == "expired":
                    order.status = OrderStatus.CANCELLED
                    logger.warning(f"Order expired: {order.alpaca_order_id}")
                    return order

                elif status == "partially_filled" and filled_qty > last_filled_qty:
                    order.partial_fill(
                        price=float(alpaca_order.filled_avg_price),
                        filled_quantity=filled_qty,
                        timestamp=alpaca_order.filled_at,
                    )
                    logger.info(
                        f"Order partially filled: {filled_qty}/{order.quantity} {order.symbol} "
                        f"@ ${order.fill_price:.2f} ({order.fill_ratio:.1%})"
                    )
                    last_filled_qty = filled_qty

                time.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error checking order status: {e}")
                time.sleep(poll_interval)

        # Timeout reached
        elapsed = time.time() - start_time
        logger.warning(f"Order fill timeout after {elapsed:.1f}s: {order.alpaca_order_id}")

        if order.filled_quantity and order.filled_quantity > 0:
            logger.info(
                f"Partial fill on timeout: {order.filled_quantity}/{order.quantity} "
                f"({order.fill_ratio:.1%})"
            )

        if cancel_on_timeout and order.status in [OrderStatus.PENDING, OrderStatus.PARTIALLY_FILLED]:
            if self.cancel_order(order.alpaca_order_id):
                if not (order.filled_quantity and order.filled_quantity > 0):
                    order.cancel()

        return order

    def submit_and_wait(
        self,
        order: Order,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> Order:
        """
        Submit an order and wait for it to be filled.

        Args:
            order: Order to submit
            timeout: Maximum wait time
            poll_interval: Status check interval

        Returns:
            Updated order with fill status
        """
        order = self.submit_order(order)

        if order.status == OrderStatus.REJECTED:
            return order

        if order.status == OrderStatus.FILLED:
            return order

        return self.wait_for_fill(order, timeout, poll_interval)
