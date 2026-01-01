"""
Tests for TradingBot loop safety - detecting infinite loops and ensuring proper exit.
"""
import signal
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestTradingBotLoopSafety:
    """Test TradingBot loop safety and exit conditions."""

    @pytest.fixture
    def mock_trading_bot_for_loop(self, mock_settings):
        """Create TradingBot specifically for loop testing."""
        with patch("trading_bot.FIRESTORE_AVAILABLE", False), \
             patch("trading_bot.AlpacaBroker") as MockBroker, \
             patch("trading_bot.DiscordNotifier") as MockDiscord, \
             patch("trading_bot.DataFetcher") as MockFetcher, \
             patch("trading_bot.TradeLogger"), \
             patch("trading_bot.AuditTrail"):

            mock_broker = Mock()
            mock_broker.get_account.return_value = {
                "account_number": "TEST",
                "equity": 10000.0,
                "buying_power": 10000.0,
            }
            mock_broker.is_market_open.return_value = False  # Start with closed market
            mock_broker.get_position.return_value = None
            MockBroker.return_value = mock_broker

            mock_discord = Mock()
            mock_discord.enabled = False
            MockDiscord.return_value = mock_discord

            MockFetcher.return_value = Mock()

            from trading_bot import TradingBot
            bot = TradingBot(mode="paper")
            bot.broker = mock_broker
            yield bot

    def test_handle_shutdown_sets_running_false_sigint(self, mock_trading_bot_for_loop):
        """Verify _handle_shutdown sets running=False for SIGINT."""
        bot = mock_trading_bot_for_loop
        bot.running = True

        # Call shutdown handler directly
        bot._handle_shutdown(signal.SIGINT, None)

        assert bot.running == False

    def test_handle_shutdown_sets_running_false_sigterm(self, mock_trading_bot_for_loop):
        """Verify _handle_shutdown sets running=False for SIGTERM."""
        bot = mock_trading_bot_for_loop
        bot.running = True

        # Call shutdown handler directly
        bot._handle_shutdown(signal.SIGTERM, None)

        assert bot.running == False

    def test_loop_respects_running_flag(self, mock_trading_bot_for_loop):
        """Verify loop respects running=False flag immediately."""
        bot = mock_trading_bot_for_loop
        bot.running = False  # Pre-set to False

        # _run_trading_loop should exit immediately
        start_time = time.time()
        bot._run_trading_loop()
        elapsed = time.time() - start_time

        assert elapsed < 1.0, "Loop did not exit immediately when running=False"

    def test_loop_handles_exception_gracefully(self, mock_trading_bot_for_loop):
        """Verify loop continues after exception without infinite loop."""
        bot = mock_trading_bot_for_loop
        bot.running = True

        call_count = [0]

        def error_then_stop(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise Exception("Simulated network error")
            if call_count[0] >= 3:
                bot.running = False
            return False

        bot.broker.is_market_open = Mock(side_effect=error_then_stop)

        # Should not raise, should exit gracefully
        with patch("time.sleep", return_value=None):  # Skip actual sleep
            bot._run_trading_loop()

        # Should have called multiple times (showing recovery after error)
        assert call_count[0] >= 2, "Loop should have recovered and continued after exception"

    def test_loop_sleeps_when_market_closed(self, mock_trading_bot_for_loop):
        """Verify loop sleeps when market is closed (not spinning CPU)."""
        bot = mock_trading_bot_for_loop
        bot.broker.is_market_open.return_value = False
        bot.running = True

        sleep_calls = []

        def track_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 2:
                bot.running = False

        with patch("time.sleep", side_effect=track_sleep):
            bot._run_trading_loop()

        assert len(sleep_calls) >= 1, "Loop should call sleep when market closed"
        assert sleep_calls[0] == 60, "Should sleep 60 seconds when market closed"


class TestTradingBotMaxIterations:
    """Test loop with iteration limits to prevent infinite loops."""

    def test_loop_terminates_with_iteration_tracking(self, mock_settings):
        """Verify we can track and limit iterations."""
        with patch("trading_bot.FIRESTORE_AVAILABLE", False), \
             patch("trading_bot.AlpacaBroker") as MockBroker, \
             patch("trading_bot.DiscordNotifier") as MockDiscord, \
             patch("trading_bot.DataFetcher"), \
             patch("trading_bot.TradeLogger"), \
             patch("trading_bot.AuditTrail"):

            mock_broker = Mock()
            mock_broker.get_account.return_value = {"account_number": "TEST", "equity": 10000.0, "buying_power": 10000.0}
            mock_broker.is_market_open.return_value = True
            mock_broker.get_position.return_value = None
            MockBroker.return_value = mock_broker

            MockDiscord.return_value.enabled = False

            from trading_bot import TradingBot
            bot = TradingBot(mode="paper")
            bot.broker = mock_broker

            # Create wrapper to count iterations
            iteration_count = [0]
            max_iterations = 5

            original_check_signals = bot._check_signals

            def counted_check():
                iteration_count[0] += 1
                if iteration_count[0] >= max_iterations:
                    bot.running = False
                # Don't actually check signals in test

            bot._check_signals = counted_check
            bot.running = True

            with patch("time.sleep", return_value=None):
                bot._run_trading_loop()

            assert iteration_count[0] == max_iterations
            assert bot.running == False


class TestTradingBotTimeout:
    """Test that operations have reasonable timeouts."""

    def test_signal_check_should_not_hang(self, mock_trading_bot):
        """Verify _check_signals doesn't hang indefinitely."""
        bot = mock_trading_bot

        # Set up data fetcher to return data
        import pandas as pd
        dates = pd.date_range(start="2024-01-01", periods=50, freq="B")
        test_data = pd.DataFrame({
            "open": [50.0] * 50,
            "high": [51.0] * 50,
            "low": [49.0] * 50,
            "close": [50.0] * 50,
            "volume": [1000000] * 50,
            "vwap": [50.0] * 50,
        }, index=dates)

        bot.data_fetcher.get_daily_bars.return_value = test_data
        bot.broker.get_position.return_value = None

        # Should complete within timeout
        start = time.time()
        bot._check_signals()
        elapsed = time.time() - start

        assert elapsed < 5.0, "_check_signals should complete quickly"
