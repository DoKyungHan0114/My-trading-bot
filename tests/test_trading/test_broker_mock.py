"""
Tests for AlpacaBroker with mocked Alpaca API.
"""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestAlpacaBrokerInit:
    """Test AlpacaBroker initialization."""

    def test_broker_initializes_with_defaults(self, mock_settings):
        """Verify broker initializes with default settings."""
        with patch("execution.broker.ALPACA_AVAILABLE", False):
            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)

            assert broker.paper == True
            assert broker.api_key is not None

    def test_broker_accepts_custom_credentials(self, mock_settings):
        """Verify broker accepts custom API credentials."""
        with patch("execution.broker.ALPACA_AVAILABLE", False):
            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(
                api_key="custom_key",
                secret_key="custom_secret",
                paper=True,
            )

            assert broker.api_key == "custom_key"
            assert broker.secret_key == "custom_secret"


class TestGetAccount:
    """Test get_account method."""

    def test_returns_mock_account_when_unavailable(self, mock_settings):
        """Verify mock account returned when Alpaca not available."""
        with patch("execution.broker.ALPACA_AVAILABLE", False):
            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            account = broker.get_account()

            assert isinstance(account, dict)
            assert account["account_number"] == "MOCK"
            assert account["equity"] == 10000.0

    def test_returns_real_account_structure(self):
        """Verify real account has expected structure."""
        with patch("execution.broker.ALPACA_AVAILABLE", True), \
             patch("execution.broker.TradingClient") as MockClient:

            mock_account = Mock()
            mock_account.account_number = "PA123"
            mock_account.status = "ACTIVE"
            mock_account.cash = 10000.0
            mock_account.buying_power = 10000.0
            mock_account.equity = 10000.0
            mock_account.portfolio_value = 10000.0
            mock_account.pattern_day_trader = False
            mock_account.trading_blocked = False
            mock_account.transfers_blocked = False

            mock_client = Mock()
            mock_client.get_account.return_value = mock_account
            MockClient.return_value = mock_client

            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            account = broker.get_account()

            assert isinstance(account, dict)
            assert account["account_number"] == "PA123"
            assert "equity" in account
            assert "buying_power" in account


class TestGetPosition:
    """Test get_position method."""

    def test_returns_none_when_no_position(self, mock_settings):
        """Verify None returned when no position exists."""
        with patch("execution.broker.ALPACA_AVAILABLE", False):
            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            position = broker.get_position("TQQQ")

            assert position is None

    def test_returns_position_structure(self):
        """Verify position has expected structure."""
        with patch("execution.broker.ALPACA_AVAILABLE", True), \
             patch("execution.broker.TradingClient") as MockClient:

            mock_position = Mock()
            mock_position.symbol = "TQQQ"
            mock_position.qty = 100.0
            mock_position.avg_entry_price = 45.0
            mock_position.market_value = 4500.0
            mock_position.cost_basis = 4500.0
            mock_position.unrealized_pl = 0.0
            mock_position.unrealized_plpc = 0.0
            mock_position.current_price = 45.0

            mock_client = Mock()
            mock_client.get_open_position.return_value = mock_position
            MockClient.return_value = mock_client

            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            position = broker.get_position("TQQQ")

            assert isinstance(position, dict)
            assert position["symbol"] == "TQQQ"
            assert position["quantity"] == 100.0


class TestSubmitOrder:
    """Test submit_order method."""

    def test_mock_order_fills_immediately(self, mock_settings):
        """Verify mock order fills immediately."""
        with patch("execution.broker.ALPACA_AVAILABLE", False):
            from execution.broker import AlpacaBroker
            from execution.orders import Order

            broker = AlpacaBroker(paper=True)
            order = Order.market_buy("TQQQ", 100.0)

            result = broker.submit_order(order)

            assert result.is_filled == True
            assert result.alpaca_order_id is not None
            assert result.fill_price > 0

    def test_order_count_increments(self, mock_settings):
        """Verify order count increments on each submission."""
        with patch("execution.broker.ALPACA_AVAILABLE", False):
            from execution.broker import AlpacaBroker
            from execution.orders import Order

            broker = AlpacaBroker(paper=True)
            initial_count = broker.order_count

            broker.submit_order(Order.market_buy("TQQQ", 50.0))
            broker.submit_order(Order.market_sell("TQQQ", 50.0))

            assert broker.order_count == initial_count + 2

    def test_real_order_submission(self):
        """Verify real order submission structure."""
        with patch("execution.broker.ALPACA_AVAILABLE", True), \
             patch("execution.broker.TradingClient") as MockClient:

            mock_result = Mock()
            mock_result.id = "order-123"
            mock_result.filled_at = datetime.utcnow()
            mock_result.filled_avg_price = 45.0
            mock_result.filled_qty = 100.0

            mock_client = Mock()
            mock_client.submit_order.return_value = mock_result
            MockClient.return_value = mock_client

            from execution.broker import AlpacaBroker
            from execution.orders import Order

            broker = AlpacaBroker(paper=True)
            order = Order.market_buy("TQQQ", 100.0)

            result = broker.submit_order(order)

            assert result.alpaca_order_id == "order-123"
            assert result.is_filled == True


class TestIsMarketOpen:
    """Test is_market_open method."""

    def test_returns_true_when_unavailable(self, mock_settings):
        """Verify returns True when Alpaca not available (for testing)."""
        with patch("execution.broker.ALPACA_AVAILABLE", False), \
             patch("execution.services.account.ALPACA_AVAILABLE", False):
            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            is_open = broker.is_market_open()

            assert is_open == True

    def test_returns_clock_status(self):
        """Verify returns actual clock status."""
        with patch("execution.broker.ALPACA_AVAILABLE", True), \
             patch("execution.broker.TradingClient") as MockClient:

            mock_clock = Mock()
            mock_clock.is_open = True

            mock_client = Mock()
            mock_client.get_clock.return_value = mock_clock
            MockClient.return_value = mock_client

            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            is_open = broker.is_market_open()

            assert is_open == True


class TestBrokerErrorHandling:
    """Test broker error handling."""

    def test_get_account_handles_api_error(self):
        """Verify get_account handles API errors gracefully."""
        with patch("execution.broker.ALPACA_AVAILABLE", True), \
             patch("execution.broker.TradingClient") as MockClient:

            mock_client = Mock()
            mock_client.get_account.side_effect = Exception("API Error")
            MockClient.return_value = mock_client

            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            account = broker.get_account()

            # Should return mock account on error
            assert account["account_number"] == "MOCK"

    def test_submit_order_handles_rejection(self):
        """Verify submit_order handles rejection gracefully."""
        with patch("execution.broker.ALPACA_AVAILABLE", True), \
             patch("execution.broker.TradingClient") as MockClient:

            mock_client = Mock()
            mock_client.submit_order.side_effect = Exception("Order rejected")
            MockClient.return_value = mock_client

            from execution.broker import AlpacaBroker
            from execution.orders import Order
            from config.constants import OrderStatus

            broker = AlpacaBroker(paper=True)
            order = Order.market_buy("TQQQ", 100.0)

            result = broker.submit_order(order)

            # Should mark order as rejected
            assert result.status == OrderStatus.REJECTED


class TestGetPositions:
    """Test get_positions method."""

    def test_returns_empty_when_unavailable(self, mock_settings):
        """Verify empty list when Alpaca not available."""
        with patch("execution.broker.ALPACA_AVAILABLE", False):
            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            positions = broker.get_positions()

            assert positions == []

    def test_returns_all_positions(self):
        """Verify all positions returned."""
        with patch("execution.broker.ALPACA_AVAILABLE", True), \
             patch("execution.broker.TradingClient") as MockClient:

            mock_pos1 = Mock()
            mock_pos1.symbol = "TQQQ"
            mock_pos1.qty = 100.0
            mock_pos1.avg_entry_price = 45.0
            mock_pos1.market_value = 4500.0
            mock_pos1.cost_basis = 4500.0
            mock_pos1.unrealized_pl = 0.0
            mock_pos1.unrealized_plpc = 0.0
            mock_pos1.current_price = 45.0
            mock_pos1.side = "long"

            mock_pos2 = Mock()
            mock_pos2.symbol = "SQQQ"
            mock_pos2.qty = 50.0
            mock_pos2.avg_entry_price = 20.0
            mock_pos2.market_value = 1000.0
            mock_pos2.cost_basis = 1000.0
            mock_pos2.unrealized_pl = 0.0
            mock_pos2.unrealized_plpc = 0.0
            mock_pos2.current_price = 20.0
            mock_pos2.side = "long"

            mock_client = Mock()
            mock_client.get_all_positions.return_value = [mock_pos1, mock_pos2]
            MockClient.return_value = mock_client

            from execution.broker import AlpacaBroker

            broker = AlpacaBroker(paper=True)
            positions = broker.get_positions()

            assert len(positions) == 2
            assert positions[0]["symbol"] == "TQQQ"
            assert positions[1]["symbol"] == "SQQQ"
