"""
Tests for weekly report generation.
"""
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

ET = pytz.timezone("America/New_York")


class TestGetWeekRange:
    """Test get_week_range function."""

    def test_returns_monday_to_friday(self):
        """Verify week range is Monday to Friday."""
        from automation.weekly_report import get_week_range

        start, end = get_week_range()

        start_dt = datetime.strptime(start, "%Y-%m-%d")
        end_dt = datetime.strptime(end, "%Y-%m-%d")

        assert start_dt.weekday() == 0  # Monday
        assert end_dt.weekday() == 4    # Friday
        assert (end_dt - start_dt).days == 4


class TestGetWeeksTrades:
    """Test get_weeks_trades function."""

    def test_returns_empty_for_no_file(self, tmp_path):
        """Verify empty list when trades file doesn't exist."""
        from automation.weekly_report import get_weeks_trades

        nonexistent = tmp_path / "nonexistent.json"
        trades = get_weeks_trades(str(nonexistent))
        assert trades == []

    def test_filters_by_week_range(self, tmp_path):
        """Verify trades are filtered to current week only."""
        from automation.weekly_report import get_week_range, get_weeks_trades

        start, end = get_week_range()

        trades_data = [
            {"timestamp_utc": f"{start}T10:00:00Z", "side": "BUY", "quantity": 100},
            {"timestamp_utc": "2024-01-01T10:00:00Z", "side": "SELL", "quantity": 50},  # Old
            {"timestamp_utc": f"{end}T14:00:00Z", "side": "SELL", "quantity": 100},
        ]

        trades_file = tmp_path / "trades.json"
        trades_file.write_text(json.dumps(trades_data))

        trades = get_weeks_trades(str(trades_file))

        # Should only include trades from current week
        assert len(trades) == 2


class TestCalculateWeeklyStats:
    """Test calculate_weekly_stats function."""

    def test_with_trades(self):
        """Verify weekly statistics calculation."""
        from automation.weekly_report import calculate_weekly_stats

        trades = [
            {"realized_pnl_usd": 100.0},
            {"realized_pnl_usd": -30.0},
            {"realized_pnl_usd": 50.0},
            {"realized_pnl_usd": 20.0},
        ]

        stats = calculate_weekly_stats(trades)

        assert stats["total_trades"] == 4
        assert stats["wins"] == 3
        assert stats["losses"] == 1
        assert stats["win_rate"] == 75.0
        assert stats["total_pnl"] == 140.0
        assert stats["best_trade"] == 100.0
        assert stats["worst_trade"] == -30.0
        assert stats["avg_pnl"] == 35.0

    def test_empty_trades(self):
        """Verify stats for no trades."""
        from automation.weekly_report import calculate_weekly_stats

        stats = calculate_weekly_stats([])

        assert stats["total_trades"] == 0
        assert stats["wins"] == 0
        assert stats["losses"] == 0
        assert stats["win_rate"] == 0
        assert stats["total_pnl"] == 0
        assert stats["best_trade"] == 0
        assert stats["worst_trade"] == 0
        assert stats["avg_pnl"] == 0

    def test_all_wins(self):
        """Verify stats with all winning trades."""
        from automation.weekly_report import calculate_weekly_stats

        trades = [
            {"realized_pnl_usd": 100.0},
            {"realized_pnl_usd": 50.0},
        ]

        stats = calculate_weekly_stats(trades)

        assert stats["win_rate"] == 100.0
        assert stats["losses"] == 0

    def test_handles_none_values(self):
        """Verify stats handle None P&L values."""
        from automation.weekly_report import calculate_weekly_stats

        trades = [
            {"realized_pnl_usd": None},
            {"realized_pnl_usd": 100.0},
        ]

        stats = calculate_weekly_stats(trades)

        assert stats["total_trades"] == 2
        assert stats["total_pnl"] == 100.0


class TestCreateWeeklyEmbed:
    """Test create_weekly_embed function."""

    def test_embed_structure(self):
        """Verify weekly embed has correct structure."""
        from automation.weekly_report import create_weekly_embed

        stats = {
            "total_trades": 10,
            "wins": 6,
            "losses": 4,
            "win_rate": 60.0,
            "total_pnl": 500.0,
            "best_trade": 200.0,
            "worst_trade": -100.0,
            "avg_pnl": 50.0,
        }

        embed = create_weekly_embed(
            week_range="2024-12-23 ~ 2024-12-27",
            equity=10000.0,
            stats=stats,
            position=None,
        )

        assert "title" in embed
        assert "Weekly Report" in embed["title"]
        assert "color" in embed
        assert "fields" in embed
        assert len(embed["fields"]) >= 7  # Portfolio, P&L, Win rate, Trades, Best, Worst, Avg

    def test_green_color_for_profit(self):
        """Verify embed color is green for positive weekly P&L."""
        from automation.weekly_report import create_weekly_embed

        stats = {"total_trades": 5, "wins": 3, "losses": 2, "win_rate": 60.0,
                 "total_pnl": 500.0, "best_trade": 200.0, "worst_trade": -50.0, "avg_pnl": 100.0}

        embed = create_weekly_embed(
            week_range="2024-12-23 ~ 2024-12-27",
            equity=10000.0,
            stats=stats,
            position=None,
        )

        assert embed["color"] == 0x00FF00  # Green

    def test_red_color_for_loss(self):
        """Verify embed color is red for negative weekly P&L."""
        from automation.weekly_report import create_weekly_embed

        stats = {"total_trades": 5, "wins": 1, "losses": 4, "win_rate": 20.0,
                 "total_pnl": -500.0, "best_trade": 50.0, "worst_trade": -200.0, "avg_pnl": -100.0}

        embed = create_weekly_embed(
            week_range="2024-12-23 ~ 2024-12-27",
            equity=10000.0,
            stats=stats,
            position=None,
        )

        assert embed["color"] == 0xFF0000  # Red


class TestSendWeeklyReport:
    """Test send_weekly_report function."""

    @patch("automation.weekly_report.get_settings")
    def test_fails_without_webhook(self, mock_settings):
        """Verify failure when weekly webhook URL not configured."""
        mock_settings.return_value.discord.weekly_webhook_url = ""

        from automation.weekly_report import send_weekly_report

        result = send_weekly_report()

        assert result == False

    @patch("automation.weekly_report.AlpacaBroker")
    @patch("automation.weekly_report.requests")
    @patch("automation.weekly_report.get_settings")
    @patch("automation.weekly_report.calculate_weekly_uptime")
    @patch("automation.weekly_report.analyze_no_trade_reason")
    @patch("automation.weekly_report.get_weeks_trades")
    def test_send_success(
        self,
        mock_get_trades,
        mock_no_trade,
        mock_uptime,
        mock_settings,
        mock_requests,
        mock_broker_class,
    ):
        """Verify successful weekly report sending."""
        mock_settings.return_value.discord.weekly_webhook_url = "https://discord.com/webhook/test"

        mock_broker = Mock()
        mock_broker.get_account.return_value = {"equity": 10000.0}
        mock_broker.get_position.return_value = None
        mock_broker_class.return_value = mock_broker

        mock_get_trades.return_value = []
        mock_uptime.return_value = []

        mock_reason = Mock()
        mock_reason.primary_reason = "No signal"
        mock_reason.market_condition = "normal"
        mock_reason.rsi_value = 45.0
        mock_no_trade.return_value = mock_reason

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_requests.post.return_value = mock_response

        from automation.weekly_report import send_weekly_report

        result = send_weekly_report()

        assert result == True
        mock_requests.post.assert_called_once()
