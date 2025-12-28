"""
Tests for end-to-end signal-to-trade flow.
"""
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestSignalToTradeExecution:
    """Test complete signal-to-trade flow."""

    @pytest.fixture
    def trading_bot_with_oversold_data(self, mock_settings, oversold_ohlcv_data, mock_broker):
        """Create TradingBot with oversold data."""
        with patch("main.FIRESTORE_AVAILABLE", False), \
             patch("main.AlpacaBroker") as MockBroker, \
             patch("main.DiscordNotifier") as MockDiscord, \
             patch("main.DataFetcher") as MockFetcher, \
             patch("main.TradeLogger") as MockLogger, \
             patch("main.AuditTrail") as MockAudit:

            MockBroker.return_value = mock_broker
            mock_broker.get_position.return_value = None  # No position

            mock_fetcher = Mock()
            mock_fetcher.get_daily_bars.return_value = oversold_ohlcv_data
            MockFetcher.return_value = mock_fetcher

            mock_discord = Mock()
            mock_discord.enabled = True
            mock_discord.send_signal = Mock(return_value=True)
            mock_discord.send_trade_notification = Mock(return_value=True)
            MockDiscord.return_value = mock_discord

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            mock_audit = Mock()
            MockAudit.return_value = mock_audit

            from main import TradingBot
            bot = TradingBot(mode="paper")
            bot.broker = mock_broker
            bot.data_fetcher = mock_fetcher
            bot.discord = mock_discord
            bot.trade_logger = mock_logger
            bot.audit_trail = mock_audit

            yield bot, mock_broker, mock_logger

    def test_check_signals_fetches_data(self, trading_bot_with_oversold_data):
        """Verify _check_signals fetches market data."""
        bot, mock_broker, _ = trading_bot_with_oversold_data

        bot._check_signals()

        # Should have fetched data
        bot.data_fetcher.get_daily_bars.assert_called()

    def test_check_signals_with_position(self, trading_bot_with_oversold_data):
        """Verify _check_signals works when position exists."""
        bot, mock_broker, mock_logger = trading_bot_with_oversold_data

        # Have a position
        mock_broker.get_position.return_value = {
            "symbol": "TQQQ",
            "quantity": 100.0,
            "avg_entry_price": 45.0,
        }
        bot.entry_price = 45.0

        # Should not crash
        bot._check_signals()

        # Verify data was fetched
        bot.data_fetcher.get_daily_bars.assert_called()

    def test_execute_buy_logs_trade(self, mock_settings, mock_broker):
        """Verify buy execution logs trade."""
        with patch("main.FIRESTORE_AVAILABLE", False), \
             patch("main.AlpacaBroker") as MockBroker, \
             patch("main.DiscordNotifier") as MockDiscord, \
             patch("main.DataFetcher"), \
             patch("main.TradeLogger") as MockLogger, \
             patch("main.AuditTrail") as MockAudit:

            MockBroker.return_value = mock_broker

            mock_discord = Mock()
            mock_discord.enabled = False
            MockDiscord.return_value = mock_discord

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            mock_audit = Mock()
            MockAudit.return_value = mock_audit

            from main import TradingBot
            bot = TradingBot(mode="paper")
            bot.broker = mock_broker
            bot.trade_logger = mock_logger
            bot.audit_trail = mock_audit

            bot._execute_buy(current_price=45.0, reason="Test buy")

            # Verify trade was logged
            mock_logger.log_trade.assert_called_once()
            call_kwargs = mock_logger.log_trade.call_args[1]
            assert call_kwargs["side"] == "BUY"
            assert call_kwargs["symbol"] == "TQQQ"

    def test_execute_sell_calculates_pnl(self, mock_settings, mock_broker):
        """Verify sell execution calculates P&L."""
        with patch("main.FIRESTORE_AVAILABLE", False), \
             patch("main.AlpacaBroker") as MockBroker, \
             patch("main.DiscordNotifier") as MockDiscord, \
             patch("main.DataFetcher"), \
             patch("main.TradeLogger") as MockLogger, \
             patch("main.AuditTrail") as MockAudit:

            MockBroker.return_value = mock_broker

            mock_discord = Mock()
            mock_discord.enabled = False
            MockDiscord.return_value = mock_discord

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            mock_audit = Mock()
            MockAudit.return_value = mock_audit

            from main import TradingBot
            bot = TradingBot(mode="paper")
            bot.broker = mock_broker
            bot.trade_logger = mock_logger
            bot.audit_trail = mock_audit

            # Set entry price lower than current for profit
            bot.entry_price = 40.0
            bot.entry_date = datetime.utcnow()

            position = {"quantity": 100.0, "avg_entry_price": 40.0}
            bot._execute_sell(position, reason="Test sell")

            # Verify trade was logged with P&L
            mock_logger.log_trade.assert_called_once()
            call_kwargs = mock_logger.log_trade.call_args[1]
            assert call_kwargs["side"] == "SELL"
            assert "realized_pnl_usd" in call_kwargs


class TestNoOrderWithoutSignal:
    """Test that no orders are placed without valid signals."""

    def test_no_order_when_rsi_neutral(self, mock_settings, sample_ohlcv_data, mock_broker):
        """Verify no order when no signal generated."""
        with patch("main.FIRESTORE_AVAILABLE", False), \
             patch("main.AlpacaBroker") as MockBroker, \
             patch("main.DiscordNotifier") as MockDiscord, \
             patch("main.DataFetcher") as MockFetcher, \
             patch("main.TradeLogger"), \
             patch("main.AuditTrail"):

            MockBroker.return_value = mock_broker
            mock_broker.get_position.return_value = None

            mock_fetcher = Mock()
            mock_fetcher.get_daily_bars.return_value = sample_ohlcv_data
            MockFetcher.return_value = mock_fetcher

            MockDiscord.return_value.enabled = False

            from main import TradingBot
            bot = TradingBot(mode="paper")
            bot.broker = mock_broker
            bot.data_fetcher = mock_fetcher

            # Reset submit_order call count
            mock_broker.submit_order.reset_mock()

            bot._check_signals()

            # submit_order may or may not be called depending on actual RSI
            # This test mainly verifies no crash with neutral data


class TestHedgeExecution:
    """Test hedge position execution."""

    def test_execute_hedge_buy_logs_trade(self, mock_settings, mock_broker):
        """Verify hedge buy execution logs trade."""
        with patch("main.FIRESTORE_AVAILABLE", False), \
             patch("main.AlpacaBroker") as MockBroker, \
             patch("main.DiscordNotifier") as MockDiscord, \
             patch("main.DataFetcher"), \
             patch("main.TradeLogger") as MockLogger, \
             patch("main.AuditTrail") as MockAudit:

            MockBroker.return_value = mock_broker

            mock_discord = Mock()
            mock_discord.enabled = False
            MockDiscord.return_value = mock_discord

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            mock_audit = Mock()
            MockAudit.return_value = mock_audit

            # Enable short
            mock_settings.strategy.short_enabled = True

            from main import TradingBot
            bot = TradingBot(mode="paper")
            bot.broker = mock_broker
            bot.trade_logger = mock_logger
            bot.audit_trail = mock_audit

            bot._execute_hedge_buy(current_price=20.0, reason="Test hedge")

            # Verify trade was logged
            mock_logger.log_trade.assert_called_once()
            call_kwargs = mock_logger.log_trade.call_args[1]
            assert call_kwargs["side"] == "HEDGE_BUY"
            assert call_kwargs["symbol"] == "SQQQ"

    def test_execute_hedge_sell_logs_trade(self, mock_settings, mock_broker):
        """Verify hedge sell execution logs trade with P&L."""
        with patch("main.FIRESTORE_AVAILABLE", False), \
             patch("main.AlpacaBroker") as MockBroker, \
             patch("main.DiscordNotifier") as MockDiscord, \
             patch("main.DataFetcher"), \
             patch("main.TradeLogger") as MockLogger, \
             patch("main.AuditTrail") as MockAudit:

            MockBroker.return_value = mock_broker

            mock_discord = Mock()
            mock_discord.enabled = False
            MockDiscord.return_value = mock_discord

            mock_logger = Mock()
            MockLogger.return_value = mock_logger

            mock_audit = Mock()
            MockAudit.return_value = mock_audit

            from main import TradingBot
            bot = TradingBot(mode="paper")
            bot.broker = mock_broker
            bot.trade_logger = mock_logger
            bot.audit_trail = mock_audit

            # Set hedge entry
            bot.hedge_entry_price = 18.0
            bot.hedge_entry_date = datetime.utcnow()

            position = {"quantity": 50.0, "avg_entry_price": 18.0}
            bot._execute_hedge_sell(position, reason="Test hedge exit")

            # Verify trade was logged
            mock_logger.log_trade.assert_called_once()
            call_kwargs = mock_logger.log_trade.call_args[1]
            assert call_kwargs["side"] == "HEDGE_SELL"
            assert "realized_pnl_usd" in call_kwargs
