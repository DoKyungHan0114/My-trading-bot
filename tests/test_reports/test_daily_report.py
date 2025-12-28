"""
Tests for daily report generation.
"""
import json
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

ET = pytz.timezone("America/New_York")


class TestGetTodaysTrades:
    """Test get_todays_trades function."""

    def test_returns_empty_for_no_file(self, tmp_path):
        """Verify empty list when trades file doesn't exist."""
        from automation.daily_report import get_todays_trades

        nonexistent = tmp_path / "nonexistent.json"
        trades = get_todays_trades(str(nonexistent))
        assert trades == []

    def test_returns_empty_for_invalid_json(self, tmp_path):
        """Verify empty list for invalid JSON."""
        from automation.daily_report import get_todays_trades

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("not valid json")
        trades = get_todays_trades(str(bad_file))
        assert trades == []

    def test_returns_empty_for_empty_trades(self, tmp_path):
        """Verify empty list when no trades exist."""
        from automation.daily_report import get_todays_trades

        trades_file = tmp_path / "trades.json"
        trades_file.write_text("[]")
        trades = get_todays_trades(str(trades_file))
        assert trades == []

    def test_filters_by_date(self, tmp_path):
        """Verify trades are filtered to today only."""
        from automation.daily_report import get_todays_trades

        today_et = datetime.now(ET).strftime("%Y-%m-%d")
        trades_data = [
            {"timestamp_utc": f"{today_et}T10:00:00Z", "side": "BUY", "quantity": 100},
            {"timestamp_utc": "2024-01-01T10:00:00Z", "side": "SELL", "quantity": 50},
            {"timestamp_utc": f"{today_et}T14:00:00Z", "side": "SELL", "quantity": 100},
        ]

        trades_file = tmp_path / "trades.json"
        trades_file.write_text(json.dumps(trades_data))

        trades = get_todays_trades(str(trades_file))
        assert len(trades) == 2
        assert all(t["timestamp_utc"].startswith(today_et) for t in trades)


class TestCalculateDailyPnl:
    """Test calculate_daily_pnl function."""

    def test_with_mixed_trades(self):
        """Verify P&L calculation with mix of wins and losses."""
        from automation.daily_report import calculate_daily_pnl

        trades = [
            {"realized_pnl_usd": 100.0},
            {"realized_pnl_usd": -50.0},
            {"realized_pnl_usd": 75.0},
        ]
        total_pnl, wins, losses = calculate_daily_pnl(trades)

        assert total_pnl == 125.0
        assert wins == 2
        assert losses == 1

    def test_handles_none_values(self):
        """Verify P&L calculation handles None realized_pnl_usd."""
        from automation.daily_report import calculate_daily_pnl

        trades = [
            {"realized_pnl_usd": None},
            {"realized_pnl_usd": 100.0},
            {},  # Missing key
        ]
        total_pnl, wins, losses = calculate_daily_pnl(trades)

        assert total_pnl == 100.0
        assert wins == 1
        assert losses == 0

    def test_empty_trades(self):
        """Verify P&L for no trades."""
        from automation.daily_report import calculate_daily_pnl

        total_pnl, wins, losses = calculate_daily_pnl([])

        assert total_pnl == 0.0
        assert wins == 0
        assert losses == 0

    def test_all_losses(self):
        """Verify P&L calculation with all losses."""
        from automation.daily_report import calculate_daily_pnl

        trades = [
            {"realized_pnl_usd": -50.0},
            {"realized_pnl_usd": -30.0},
        ]
        total_pnl, wins, losses = calculate_daily_pnl(trades)

        assert total_pnl == -80.0
        assert wins == 0
        assert losses == 2


class TestCreateDailyEmbed:
    """Test create_daily_embed function."""

    def test_embed_structure(self):
        """Verify daily embed has correct structure."""
        from automation.daily_report import create_daily_embed

        embed = create_daily_embed(
            date="2024-12-28",
            equity=10000.0,
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            trades=[],
            wins=0,
            losses=0,
            position=None,
        )

        assert "title" in embed
        assert "Daily Report" in embed["title"]
        assert "color" in embed
        assert "fields" in embed
        assert len(embed["fields"]) >= 4  # Portfolio, P&L, Trades, Position

    def test_green_color_for_profit(self):
        """Verify embed color is green for positive P&L."""
        from automation.daily_report import create_daily_embed

        embed = create_daily_embed(
            date="2024-12-28",
            equity=10000.0,
            daily_pnl=100.0,
            daily_pnl_pct=1.0,
            trades=[],
            wins=1,
            losses=0,
            position=None,
        )

        assert embed["color"] == 0x00FF00  # Green

    def test_red_color_for_loss(self):
        """Verify embed color is red for negative P&L."""
        from automation.daily_report import create_daily_embed

        embed = create_daily_embed(
            date="2024-12-28",
            equity=10000.0,
            daily_pnl=-100.0,
            daily_pnl_pct=-1.0,
            trades=[],
            wins=0,
            losses=1,
            position=None,
        )

        assert embed["color"] == 0xFF0000  # Red

    def test_gray_color_for_no_change(self):
        """Verify embed color is gray for zero P&L."""
        from automation.daily_report import create_daily_embed

        embed = create_daily_embed(
            date="2024-12-28",
            equity=10000.0,
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            trades=[],
            wins=0,
            losses=0,
            position=None,
        )

        assert embed["color"] == 0x808080  # Gray

    def test_includes_position_info(self, mock_alpaca_position):
        """Verify position info is included in embed."""
        from automation.daily_report import create_daily_embed

        embed = create_daily_embed(
            date="2024-12-28",
            equity=10000.0,
            daily_pnl=0.0,
            daily_pnl_pct=0.0,
            trades=[],
            wins=0,
            losses=0,
            position=mock_alpaca_position,
        )

        position_field = next(f for f in embed["fields"] if "Position" in f["name"])
        assert "TQQQ" in position_field["value"]

    def test_includes_trade_details(self):
        """Verify trade details are included when trades exist."""
        from automation.daily_report import create_daily_embed

        trades = [
            {"side": "BUY", "quantity": 100, "fill_price": 45.0, "realized_pnl_usd": None},
            {"side": "SELL", "quantity": 100, "fill_price": 46.0, "realized_pnl_usd": 100.0},
        ]

        embed = create_daily_embed(
            date="2024-12-28",
            equity=10000.0,
            daily_pnl=100.0,
            daily_pnl_pct=1.0,
            trades=trades,
            wins=1,
            losses=0,
            position=None,
        )

        field_names = [f["name"] for f in embed["fields"]]
        assert any("Trade" in name for name in field_names)


class TestSendDailyReport:
    """Test send_daily_report function."""

    @patch("automation.daily_report.AlpacaBroker")
    @patch("automation.daily_report.requests")
    @patch("automation.daily_report.get_settings")
    @patch("automation.daily_report.calculate_daily_uptime")
    @patch("automation.daily_report.get_todays_trades")
    def test_send_success(
        self,
        mock_get_trades,
        mock_uptime,
        mock_settings,
        mock_requests,
        mock_broker_class,
    ):
        """Verify successful report sending."""
        # Setup mocks
        mock_settings.return_value.discord.daily_webhook_url = "https://discord.com/webhook/test"

        mock_broker = Mock()
        mock_broker.get_account.return_value = {"equity": 10000.0}
        mock_broker.get_position.return_value = None
        mock_broker_class.return_value = mock_broker

        mock_get_trades.return_value = []

        mock_uptime_result = Mock()
        mock_uptime_result.uptime_pct = 100
        mock_uptime_result.bot_running_minutes = 390
        mock_uptime_result.errors = []
        mock_uptime.return_value = mock_uptime_result

        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_requests.post.return_value = mock_response

        from automation.daily_report import send_daily_report

        result = send_daily_report()

        assert result == True
        mock_requests.post.assert_called_once()

    @patch("automation.daily_report.get_settings")
    def test_fails_without_webhook(self, mock_settings):
        """Verify failure when webhook URL not configured."""
        mock_settings.return_value.discord.daily_webhook_url = ""

        from automation.daily_report import send_daily_report

        result = send_daily_report()

        assert result == False
