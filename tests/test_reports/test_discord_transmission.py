"""
Tests for Discord webhook transmission.
"""
import sys
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestDiscordNotifier:
    """Test DiscordNotifier class."""

    def test_notifier_disabled_without_webhook(self):
        """Verify notifier is disabled when no webhook URL."""
        with patch("notifications.discord.get_settings") as mock_settings:
            mock_settings.return_value.discord.webhook_url = ""

            from notifications.discord import DiscordNotifier
            notifier = DiscordNotifier()

            assert notifier.enabled == False

    def test_notifier_enabled_with_webhook(self):
        """Verify notifier is enabled when webhook URL provided."""
        from notifications.discord import DiscordNotifier
        notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/test")

        assert notifier.enabled == True

    def test_send_message_returns_false_when_disabled(self):
        """Verify send_message returns False when disabled."""
        with patch("notifications.discord.get_settings") as mock_settings:
            mock_settings.return_value.discord.webhook_url = ""

            from notifications.discord import DiscordNotifier
            notifier = DiscordNotifier()

            result = notifier.send_message("test")
            assert result == False

    def test_send_message_truncates_long_content(self, mock_discord_notifier):
        """Verify long messages are truncated."""
        notifier, mock_requests = mock_discord_notifier

        long_message = "x" * 3000  # Exceeds Discord limit
        notifier.send_message(long_message)

        call_args = mock_requests.post.call_args
        sent_content = call_args[1]["json"]["content"]
        assert len(sent_content) <= 2000
        assert sent_content.endswith("...")

    def test_send_embed_success(self, mock_discord_notifier):
        """Verify embed sending works correctly."""
        notifier, mock_requests = mock_discord_notifier

        embed = {"title": "Test", "color": 0x00FF00}
        result = notifier.send_embed(embed)

        assert result == True
        mock_requests.post.assert_called_once()
        call_args = mock_requests.post.call_args
        assert "embeds" in call_args[1]["json"]

    def test_send_trade_notification(self, mock_discord_notifier):
        """Verify trade notification format."""
        notifier, mock_requests = mock_discord_notifier

        result = notifier.send_trade_notification(
            symbol="TQQQ",
            side="BUY",
            quantity=100.0,
            price=45.0,
            reason="RSI oversold",
        )

        assert result == True
        mock_requests.post.assert_called_once()

    def test_send_signal(self, mock_discord_notifier):
        """Verify signal notification format."""
        notifier, mock_requests = mock_discord_notifier

        result = notifier.send_signal(
            signal_type="BUY",
            symbol="TQQQ",
            price=45.0,
            rsi=25.0,
            reason="RSI oversold",
        )

        assert result == True
        mock_requests.post.assert_called_once()

    def test_send_error_alert(self, mock_discord_notifier):
        """Verify error alert format."""
        notifier, mock_requests = mock_discord_notifier

        result = notifier.send_error_alert(
            error_type="ConnectionError",
            message="Failed to connect",
            context="Trading loop",
        )

        assert result == True
        mock_requests.post.assert_called_once()

    def test_handles_request_exception(self):
        """Verify graceful handling of request exceptions."""
        with patch("notifications.discord.requests") as mock_requests:
            import requests
            mock_requests.post.side_effect = requests.exceptions.RequestException("Network error")
            mock_requests.exceptions = requests.exceptions

            from notifications.discord import DiscordNotifier
            notifier = DiscordNotifier(webhook_url="https://discord.com/api/webhooks/test/test")

            result = notifier.send_message("test")
            assert result == False


@pytest.mark.integration
class TestDiscordIntegration:
    """Integration tests with real Discord webhook (test channel)."""

    def test_send_test_message_to_discord(self, test_discord_webhook_url):
        """Send actual test message to Discord test channel."""
        from notifications.discord import DiscordNotifier

        notifier = DiscordNotifier(webhook_url=test_discord_webhook_url)
        result = notifier.send_message("[TEST] Automated test message - please ignore")

        assert result == True

    def test_send_test_embed_to_discord(self, test_discord_webhook_url):
        """Send actual test embed to Discord test channel."""
        from notifications.discord import DiscordNotifier

        notifier = DiscordNotifier(webhook_url=test_discord_webhook_url)
        embed = {
            "title": "[TEST] Daily Report Test",
            "color": 0x808080,
            "description": "This is an automated test embed - please ignore",
            "fields": [
                {"name": "Test Field", "value": "Test Value", "inline": True}
            ],
        }
        result = notifier.send_embed(embed)

        assert result == True

    def test_connection_test(self, test_discord_webhook_url):
        """Test webhook connection."""
        from notifications.discord import DiscordNotifier

        notifier = DiscordNotifier(webhook_url=test_discord_webhook_url)
        result = notifier.test_connection()

        assert result == True
