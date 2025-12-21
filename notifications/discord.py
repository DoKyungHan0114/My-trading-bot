"""
Discord webhook notifications.
"""
import json
import logging
from typing import Optional

import requests

from config.constants import DISCORD_MAX_MESSAGE_LENGTH
from config.settings import get_settings
from notifications.templates import MessageTemplates
from backtest.engine import BacktestResult

logger = logging.getLogger(__name__)


class DiscordNotifier:
    """Send notifications via Discord webhook."""

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Discord notifier.

        Args:
            webhook_url: Discord webhook URL
        """
        settings = get_settings()
        self.webhook_url = webhook_url or settings.discord.webhook_url
        self.enabled = bool(self.webhook_url)
        self.templates = MessageTemplates()

    def _send(self, payload: dict) -> bool:
        """
        Send payload to Discord webhook.

        Args:
            payload: Discord message payload

        Returns:
            True if successful
        """
        if not self.enabled:
            logger.debug("Discord notifications disabled")
            return False

        try:
            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=10,
            )
            response.raise_for_status()
            logger.debug("Discord notification sent")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to send Discord notification: {e}")
            return False

    def send_message(self, content: str) -> bool:
        """
        Send simple text message.

        Args:
            content: Message content

        Returns:
            True if successful
        """
        if len(content) > DISCORD_MAX_MESSAGE_LENGTH:
            content = content[:DISCORD_MAX_MESSAGE_LENGTH - 3] + "..."

        return self._send({"content": content})

    def send_embed(self, embed: dict) -> bool:
        """
        Send embed message.

        Args:
            embed: Discord embed dictionary

        Returns:
            True if successful
        """
        return self._send({"embeds": [embed]})

    def send_backtest_report(self, result: BacktestResult) -> bool:
        """
        Send backtest report.

        Args:
            result: BacktestResult object

        Returns:
            True if successful
        """
        embed = self.templates.backtest_report(result)
        return self.send_embed(embed)

    def send_trade_notification(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        pnl: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        reason: str = "",
    ) -> bool:
        """
        Send trade execution notification.

        Args:
            symbol: Stock symbol
            side: BUY or SELL
            quantity: Number of shares
            price: Execution price
            pnl: Realized P&L
            pnl_pct: P&L percentage
            reason: Trade reason

        Returns:
            True if successful
        """
        embed = self.templates.trade_executed(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            pnl=pnl,
            pnl_pct=pnl_pct,
            reason=reason,
        )
        return self.send_embed(embed)

    def send_error_alert(
        self,
        error_type: str,
        message: str,
        context: str = "",
    ) -> bool:
        """
        Send error alert.

        Args:
            error_type: Type of error
            message: Error message
            context: Additional context

        Returns:
            True if successful
        """
        embed = self.templates.error_alert(
            error_type=error_type,
            message=message,
            context=context,
        )
        return self.send_embed(embed)

    def send_signal(
        self,
        signal_type: str,
        symbol: str,
        price: float,
        rsi: float,
        reason: str,
    ) -> bool:
        """
        Send signal notification.

        Args:
            signal_type: BUY, SELL, or HOLD
            symbol: Stock symbol
            price: Current price
            rsi: RSI value
            reason: Signal reason

        Returns:
            True if successful
        """
        embed = self.templates.signal_generated(
            signal_type=signal_type,
            symbol=symbol,
            price=price,
            rsi=rsi,
            reason=reason,
        )
        return self.send_embed(embed)

    def send_daily_summary(
        self,
        date: str,
        portfolio_value: float,
        daily_pnl: float,
        daily_pnl_pct: float,
        positions: list[dict],
    ) -> bool:
        """
        Send daily summary.

        Args:
            date: Summary date
            portfolio_value: Current portfolio value
            daily_pnl: Daily P&L
            daily_pnl_pct: Daily P&L percentage
            positions: Current positions

        Returns:
            True if successful
        """
        embed = self.templates.daily_summary(
            date=date,
            portfolio_value=portfolio_value,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            positions=positions,
        )
        return self.send_embed(embed)

    def test_connection(self) -> bool:
        """
        Test webhook connection.

        Returns:
            True if connection successful
        """
        return self.send_message("🔔 TQQQ Trading System - Connection Test")
