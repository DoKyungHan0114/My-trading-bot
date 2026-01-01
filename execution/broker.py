"""
Alpaca broker integration for order execution.

This module now uses the refactored service classes internally
while maintaining backward compatibility with existing code.

For new code, consider using the services directly:
- execution.services.account.AccountService
- execution.services.order.OrderService
- execution.services.retry.RetryService
"""
import logging
from typing import Optional

try:
    from alpaca.trading.client import TradingClient
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

from config.settings import get_settings
from execution.orders import Order

# Import refactored services
from execution.services.retry import RetryConfig
from execution.services.account import AccountService
from execution.services.order import OrderService

logger = logging.getLogger(__name__)


class AlpacaBroker:
    """
    Alpaca trading broker for order execution.

    This is a facade that delegates to specialized services:
    - AccountService: Account and position queries
    - OrderService: Order submission and management

    For new code, consider using these services directly.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
        retry_config: Optional[RetryConfig] = None,
    ):
        """
        Initialize Alpaca broker.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            paper: Use paper trading (default True)
            retry_config: Configuration for retry behavior
        """
        settings = get_settings()
        self.api_key = api_key or settings.alpaca.api_key
        self.secret_key = secret_key or settings.alpaca.secret_key
        self.paper = paper
        self.retry_config = retry_config or RetryConfig()
        self._client: Optional[TradingClient] = None

        # Initialize services (will set client lazily)
        self._account_service = AccountService(
            api_key=self.api_key,
            secret_key=self.secret_key,
            paper=self.paper,
        )
        self._order_service = OrderService(retry_config=self.retry_config)

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
            # Share client with services
            self._account_service.set_client(self._client)
            self._order_service.client = self._client
        return self._client

    @property
    def order_count(self) -> int:
        """Get total orders placed."""
        return self._order_service.order_count

    # Expose services for direct access
    @property
    def account_service(self) -> AccountService:
        """Get account service for direct access."""
        return self._account_service

    @property
    def order_service(self) -> OrderService:
        """Get order service for direct access."""
        return self._order_service

    def get_account(self) -> dict:
        """
        Get account information.

        Returns:
            Account details dictionary
        """
        # Ensure client is initialized for services
        if ALPACA_AVAILABLE:
            _ = self.client  # Initialize client
        return self._account_service.get_account()

    def get_positions(self) -> list[dict]:
        """
        Get all open positions.

        Returns:
            List of position dictionaries
        """
        if ALPACA_AVAILABLE:
            _ = self.client  # Initialize client
        return self._account_service.get_positions()

    def get_position(self, symbol: str) -> Optional[dict]:
        """
        Get position for a specific symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position dictionary or None
        """
        if ALPACA_AVAILABLE:
            _ = self.client  # Initialize client
        return self._account_service.get_position(symbol)

    def submit_order(self, order: Order) -> Order:
        """
        Submit order to Alpaca with retry logic.

        Args:
            order: Order to submit

        Returns:
            Updated order with Alpaca order ID
        """
        if ALPACA_AVAILABLE:
            _ = self.client  # Initialize client
        return self._order_service.submit_order(order)

    def get_order(self, order_id: str) -> Optional[dict]:
        """
        Get order status.

        Args:
            order_id: Alpaca order ID

        Returns:
            Order details or None
        """
        if ALPACA_AVAILABLE:
            _ = self.client
        return self._order_service.get_order(order_id)

    def cancel_order(self, order_id: str) -> bool:
        """
        Cancel an order.

        Args:
            order_id: Alpaca order ID

        Returns:
            True if cancelled successfully
        """
        if ALPACA_AVAILABLE:
            _ = self.client
        return self._order_service.cancel_order(order_id)

    def cancel_all_orders(self) -> int:
        """
        Cancel all open orders.

        Returns:
            Number of orders cancelled
        """
        if ALPACA_AVAILABLE:
            _ = self.client
        return self._order_service.cancel_all_orders()

    def close_position(self, symbol: str) -> Optional[dict]:
        """
        Close entire position in a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Close order details or None
        """
        if ALPACA_AVAILABLE:
            _ = self.client
        return self._order_service.close_position(symbol)

    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        if ALPACA_AVAILABLE:
            _ = self.client
        return self._account_service.is_market_open()

    def wait_for_fill(
        self,
        order: Order,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
        cancel_on_timeout: bool = True,
    ) -> Order:
        """
        Wait for an order to be filled, handling partial fills.

        Args:
            order: Order to wait for
            timeout: Maximum time to wait in seconds
            poll_interval: Time between status checks in seconds
            cancel_on_timeout: Whether to cancel unfilled orders on timeout

        Returns:
            Updated order with fill status
        """
        if ALPACA_AVAILABLE:
            _ = self.client
        return self._order_service.wait_for_fill(
            order, timeout, poll_interval, cancel_on_timeout
        )

    def submit_and_wait(
        self,
        order: Order,
        timeout: float = 60.0,
        poll_interval: float = 1.0,
    ) -> Order:
        """
        Submit an order and wait for it to be filled.

        Convenience method that combines submit_order and wait_for_fill.

        Args:
            order: Order to submit and wait for
            timeout: Maximum time to wait for fill in seconds
            poll_interval: Time between status checks in seconds

        Returns:
            Updated order with fill status
        """
        if ALPACA_AVAILABLE:
            _ = self.client
        return self._order_service.submit_and_wait(order, timeout, poll_interval)
