"""
Shared pytest fixtures for TQQQ trading system tests.
"""
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Generator
from unittest.mock import Mock, patch, MagicMock

import pandas as pd
import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ==============================================
# Sample OHLCV Data Fixtures
# ==============================================

@pytest.fixture
def sample_ohlcv_data() -> pd.DataFrame:
    """Generate sample OHLCV data for testing (neutral RSI)."""
    dates = pd.date_range(start="2024-01-01", periods=100, freq="B")
    data = {
        "open": [50 + i * 0.1 for i in range(100)],
        "high": [51 + i * 0.1 for i in range(100)],
        "low": [49 + i * 0.1 for i in range(100)],
        "close": [50.5 + i * 0.1 for i in range(100)],
        "volume": [1000000 for _ in range(100)],
        "vwap": [50.3 + i * 0.1 for i in range(100)],
    }
    return pd.DataFrame(data, index=dates)


@pytest.fixture
def oversold_ohlcv_data() -> pd.DataFrame:
    """Generate OHLCV data with RSI in oversold territory (sharp decline)."""
    dates = pd.date_range(start="2024-01-01", periods=50, freq="B")
    # Create more aggressive decline pattern to ensure RSI < 30
    # Start high and drop sharply at the end
    prices = []
    for i in range(50):
        if i < 40:
            prices.append(60 - i * 0.2)  # Slow decline
        else:
            prices.append(60 - 40 * 0.2 - (i - 40) * 2)  # Sharp drop at end

    return pd.DataFrame({
        "open": [p + 0.5 for p in prices],
        "high": [p + 1 for p in prices],
        "low": [p - 0.5 for p in prices],
        "close": prices,
        "volume": [1000000 for _ in range(50)],
        "vwap": [p + 1 for p in prices],  # Price below VWAP for filter
    }, index=dates)


@pytest.fixture
def overbought_ohlcv_data() -> pd.DataFrame:
    """Generate OHLCV data with RSI in overbought territory (sharp rise)."""
    dates = pd.date_range(start="2024-01-01", periods=50, freq="B")
    # Sharp rise to trigger overbought RSI
    prices = [30 + i * 0.8 for i in range(50)]
    return pd.DataFrame({
        "open": [p - 0.5 for p in prices],
        "high": [p + 0.5 for p in prices],
        "low": [p - 1 for p in prices],
        "close": prices,
        "volume": [1000000 for _ in range(50)],
        "vwap": [p + 0.5 for p in prices],  # Price above VWAP
    }, index=dates)


# ==============================================
# Mock Alpaca API Fixtures
# ==============================================

@pytest.fixture
def mock_alpaca_account() -> dict:
    """Mock Alpaca account data."""
    return {
        "account_number": "TEST123",
        "status": "ACTIVE",
        "cash": 10000.0,
        "buying_power": 10000.0,
        "equity": 10000.0,
        "portfolio_value": 10000.0,
        "pattern_day_trader": False,
        "trading_blocked": False,
        "transfers_blocked": False,
    }


@pytest.fixture
def mock_alpaca_position() -> dict:
    """Mock Alpaca position data."""
    return {
        "symbol": "TQQQ",
        "quantity": 100.0,
        "avg_entry_price": 45.0,
        "market_value": 4500.0,
        "cost_basis": 4500.0,
        "unrealized_pl": 0.0,
        "unrealized_plpc": 0.0,
        "current_price": 45.0,
    }


@pytest.fixture
def mock_broker(mock_alpaca_account, mock_alpaca_position):
    """Create a mocked AlpacaBroker."""
    with patch("execution.broker.ALPACA_AVAILABLE", False):
        from execution.broker import AlpacaBroker

        broker = AlpacaBroker(paper=True)
        broker.get_account = Mock(return_value=mock_alpaca_account)
        broker.get_position = Mock(return_value=mock_alpaca_position)
        broker.get_positions = Mock(return_value=[mock_alpaca_position])
        broker.is_market_open = Mock(return_value=True)

        # Mock order submission
        def mock_submit(order):
            order.alpaca_order_id = f"MOCK-{order.order_id[:8]}"
            order.fill(price=45.0, quantity=order.quantity, timestamp=datetime.utcnow())
            return order

        broker.submit_order = Mock(side_effect=mock_submit)

        yield broker


# ==============================================
# Discord Fixtures
# ==============================================

@pytest.fixture
def mock_discord_notifier():
    """Create a mocked DiscordNotifier with tracked requests."""
    with patch("notifications.discord.requests") as mock_requests:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.raise_for_status = Mock()
        mock_requests.post.return_value = mock_response

        from notifications.discord import DiscordNotifier
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/test")
        yield notifier, mock_requests


@pytest.fixture
def test_discord_webhook_url() -> str:
    """Return test Discord webhook URL from environment."""
    url = os.getenv("DISCORD_TEST_WEBHOOK_URL", "")
    if not url:
        pytest.skip("DISCORD_TEST_WEBHOOK_URL not set")
    return url


# ==============================================
# Settings Fixtures
# ==============================================

@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    # Patch at the module level where get_settings is used
    with patch("config.settings.get_settings") as mock_get, \
         patch("strategy.signals.get_settings") as mock_signal_settings, \
         patch("execution.broker.get_settings") as mock_broker_settings, \
         patch("notifications.discord.get_settings") as mock_discord_settings:
        from config.settings import Settings, StrategyConfig, AlpacaConfig, DiscordConfig

        settings = Settings()
        settings.strategy = StrategyConfig()
        settings.strategy.rsi_period = 2
        settings.strategy.rsi_oversold = 30.0
        settings.strategy.rsi_overbought = 70.0  # Standard value
        settings.strategy.sma_period = 20
        settings.strategy.stop_loss_pct = 0.05
        settings.strategy.symbol = "TQQQ"
        settings.strategy.inverse_symbol = "SQQQ"
        settings.strategy.short_enabled = False
        settings.strategy.use_inverse_etf = True
        settings.strategy.vwap_filter_enabled = False
        settings.strategy.bb_filter_enabled = False
        settings.strategy.volume_filter_enabled = False
        settings.strategy.bb_period = 20
        settings.strategy.bb_std_dev = 2.0
        settings.strategy.volume_avg_period = 20
        settings.strategy.volume_min_ratio = 1.0
        settings.strategy.rsi_overbought_short = 90.0
        settings.strategy.rsi_oversold_short = 60.0
        settings.strategy.short_stop_loss_pct = 0.02
        settings.strategy.short_position_size_pct = 0.5

        settings.alpaca = AlpacaConfig()
        settings.alpaca.api_key = "test_key"
        settings.alpaca.secret_key = "test_secret"
        settings.alpaca.validate = Mock(return_value=True)

        settings.discord = DiscordConfig()
        settings.discord.webhook_url = "https://discord.com/api/webhooks/test/test"
        settings.discord.daily_webhook_url = "https://discord.com/api/webhooks/test/daily"
        settings.discord.weekly_webhook_url = "https://discord.com/api/webhooks/test/weekly"
        settings.discord.enabled = True

        mock_get.return_value = settings
        mock_signal_settings.return_value = settings
        mock_broker_settings.return_value = settings
        mock_discord_settings.return_value = settings
        yield settings


# ==============================================
# Trade Data Fixtures
# ==============================================

@pytest.fixture
def sample_trades() -> list:
    """Sample trade data for testing reports."""
    today = datetime.now().strftime("%Y-%m-%d")
    return [
        {
            "timestamp_utc": f"{today}T10:00:00Z",
            "side": "BUY",
            "quantity": 100.0,
            "fill_price": 45.0,
            "realized_pnl_usd": None,
        },
        {
            "timestamp_utc": f"{today}T14:00:00Z",
            "side": "SELL",
            "quantity": 100.0,
            "fill_price": 46.0,
            "realized_pnl_usd": 100.0,
        },
        {
            "timestamp_utc": f"{today}T15:00:00Z",
            "side": "BUY",
            "quantity": 50.0,
            "fill_price": 45.5,
            "realized_pnl_usd": None,
        },
    ]


@pytest.fixture
def temp_trades_file(tmp_path, sample_trades) -> Path:
    """Create temporary trades.json file."""
    trades_file = tmp_path / "trades.json"
    trades_file.write_text(json.dumps(sample_trades))
    return trades_file


# ==============================================
# Trading Bot Fixtures
# ==============================================

@pytest.fixture
def mock_trading_bot(mock_settings, mock_broker):
    """Create TradingBot with mocked dependencies."""
    with patch("trading_bot.FIRESTORE_AVAILABLE", False), \
         patch("trading_bot.AlpacaBroker") as MockBroker, \
         patch("trading_bot.DiscordNotifier") as MockDiscord, \
         patch("trading_bot.DataFetcher") as MockFetcher, \
         patch("trading_bot.TradeLogger") as MockLogger, \
         patch("trading_bot.AuditTrail") as MockAudit:

        MockBroker.return_value = mock_broker

        mock_discord = Mock()
        mock_discord.enabled = False
        mock_discord.send_message = Mock(return_value=True)
        mock_discord.send_trade_notification = Mock(return_value=True)
        MockDiscord.return_value = mock_discord

        mock_fetcher = Mock()
        MockFetcher.return_value = mock_fetcher

        mock_logger = Mock()
        MockLogger.return_value = mock_logger

        mock_audit = Mock()
        MockAudit.return_value = mock_audit

        from trading_bot import TradingBot
        bot = TradingBot(mode="paper")
        bot.broker = mock_broker
        bot.discord = mock_discord
        bot.data_fetcher = mock_fetcher
        bot.trade_logger = mock_logger
        bot.audit_trail = mock_audit

        yield bot


# ==============================================
# Scheduler Fixtures
# ==============================================

@pytest.fixture
def mock_scheduler():
    """Create AutomationScheduler with mocked dependencies."""
    import sys

    # Mock sklearn before importing any modules that use it
    mock_sklearn = MagicMock()
    mock_sklearn.feature_extraction = MagicMock()
    mock_sklearn.feature_extraction.text = MagicMock()
    mock_sklearn.feature_extraction.text.TfidfVectorizer = MagicMock()
    mock_sklearn.metrics = MagicMock()
    mock_sklearn.metrics.pairwise = MagicMock()
    mock_sklearn.metrics.pairwise.cosine_similarity = MagicMock(return_value=[[1.0]])
    sys.modules['sklearn'] = mock_sklearn
    sys.modules['sklearn.feature_extraction'] = mock_sklearn.feature_extraction
    sys.modules['sklearn.feature_extraction.text'] = mock_sklearn.feature_extraction.text
    sys.modules['sklearn.metrics'] = mock_sklearn.metrics
    sys.modules['sklearn.metrics.pairwise'] = mock_sklearn.metrics.pairwise

    # Create mock instances before patching
    mock_analyzer = MagicMock()
    mock_analyzer.analyze.return_value = None

    mock_report_gen = MagicMock()
    mock_report = MagicMock()
    mock_report.recent_performance = None
    mock_report_gen.generate_report.return_value = mock_report
    mock_report_gen.save_report.return_value = "/tmp/test_report.json"

    mock_discord = MagicMock()
    mock_discord.enabled = False
    mock_discord.send_message.return_value = True
    mock_discord.send_error_alert.return_value = True

    with patch("automation.scheduler.ClaudeAnalyzer", return_value=mock_analyzer), \
         patch("automation.scheduler.ReportGenerator", return_value=mock_report_gen), \
         patch("automation.scheduler.DiscordNotifier", return_value=mock_discord), \
         patch("automation.scheduler.FirestoreClient"):

        from automation.scheduler import AutomationScheduler, ScheduleConfig

        config = ScheduleConfig(
            analysis_times=[(11, 0), (14, 30)],
            auto_apply=False,
            dry_run=True,
        )
        scheduler = AutomationScheduler(config=config, firestore_client=None)
        scheduler.discord = mock_discord
        scheduler.report_gen = mock_report_gen
        scheduler.analyzer = mock_analyzer

        yield scheduler
