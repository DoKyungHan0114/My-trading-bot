"""
Message templates for Discord notifications.
"""
from datetime import datetime
from typing import Optional

from backtest.engine import BacktestResult


class MessageTemplates:
    """Templates for Discord messages."""

    @staticmethod
    def backtest_report(result: BacktestResult) -> dict:
        """
        Generate Discord embed for backtest report.

        Args:
            result: BacktestResult object

        Returns:
            Discord embed dictionary
        """
        metrics = result.metrics
        resources = result.resource_usage

        # Determine color based on performance
        if metrics.total_return_pct > 0:
            color = 0x00FF00  # Green
        elif metrics.total_return_pct > -5:
            color = 0xFFFF00  # Yellow
        else:
            color = 0xFF0000  # Red

        embed = {
            "title": "📊 Backtest Report - RSI(2) TQQQ",
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "📅 Period",
                    "value": f"{result.start_date} → {result.end_date}",
                    "inline": False,
                },
                {
                    "name": "💰 Returns",
                    "value": (
                        f"**Total**: {metrics.total_return_pct:+.2f}%\n"
                        f"**CAGR**: {metrics.cagr:+.2f}%\n"
                        f"**Final**: ${result.final_equity:,.2f}"
                    ),
                    "inline": True,
                },
                {
                    "name": "📈 Risk Metrics",
                    "value": (
                        f"**Sharpe**: {metrics.sharpe_ratio:.2f}\n"
                        f"**MDD**: {metrics.max_drawdown:.2f}%\n"
                        f"**Volatility**: {metrics.volatility:.2f}%"
                    ),
                    "inline": True,
                },
                {
                    "name": "🎯 Trade Stats",
                    "value": (
                        f"**Trades**: {metrics.total_trades}\n"
                        f"**Win Rate**: {metrics.win_rate:.1f}%\n"
                        f"**Profit Factor**: {metrics.profit_factor:.2f}"
                    ),
                    "inline": True,
                },
                {
                    "name": "⚙️ Resources",
                    "value": (
                        f"**Time**: {resources.execution_time_seconds:.2f}s\n"
                        f"**Memory**: {resources.peak_memory_mb:.1f}MB\n"
                        f"**API Calls**: {resources.api_calls}"
                    ),
                    "inline": True,
                },
            ],
            "footer": {
                "text": "RSI(2) Mean Reversion Strategy | TQQQ",
            },
        }

        return embed

    @staticmethod
    def trade_executed(
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        pnl: Optional[float] = None,
        pnl_pct: Optional[float] = None,
        reason: str = "",
    ) -> dict:
        """
        Generate Discord embed for trade execution.

        Args:
            symbol: Stock symbol
            side: BUY or SELL
            quantity: Number of shares
            price: Execution price
            pnl: Realized P&L (for sells)
            pnl_pct: P&L percentage
            reason: Signal reason

        Returns:
            Discord embed dictionary
        """
        if side == "BUY":
            color = 0x00FF00  # Green
            emoji = "🟢"
        else:
            color = 0xFF6B6B if (pnl and pnl < 0) else 0x00FF00
            emoji = "🔴" if (pnl and pnl < 0) else "🟢"

        fields = [
            {
                "name": "Symbol",
                "value": symbol,
                "inline": True,
            },
            {
                "name": "Side",
                "value": f"{emoji} {side}",
                "inline": True,
            },
            {
                "name": "Quantity",
                "value": f"{quantity:.4f}",
                "inline": True,
            },
            {
                "name": "Price",
                "value": f"${price:.2f}",
                "inline": True,
            },
        ]

        if pnl is not None:
            fields.append({
                "name": "P&L",
                "value": f"${pnl:+.2f} ({pnl_pct:+.2f}%)" if pnl_pct else f"${pnl:+.2f}",
                "inline": True,
            })

        if reason:
            fields.append({
                "name": "Reason",
                "value": reason,
                "inline": False,
            })

        embed = {
            "title": f"📈 Trade Executed - {side} {symbol}",
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": fields,
        }

        return embed

    @staticmethod
    def error_alert(
        error_type: str,
        message: str,
        context: str = "",
    ) -> dict:
        """
        Generate Discord embed for error alert.

        Args:
            error_type: Type of error
            message: Error message
            context: Additional context

        Returns:
            Discord embed dictionary
        """
        embed = {
            "title": "🚨 Error Alert",
            "color": 0xFF0000,  # Red
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Error Type",
                    "value": error_type,
                    "inline": True,
                },
                {
                    "name": "Message",
                    "value": message[:1024],  # Discord field limit
                    "inline": False,
                },
            ],
        }

        if context:
            embed["fields"].append({
                "name": "Context",
                "value": context[:1024],
                "inline": False,
            })

        return embed

    @staticmethod
    def daily_summary(
        date: str,
        portfolio_value: float,
        daily_pnl: float,
        daily_pnl_pct: float,
        positions: list[dict],
    ) -> dict:
        """
        Generate Discord embed for daily summary.

        Args:
            date: Summary date
            portfolio_value: Current portfolio value
            daily_pnl: Daily P&L
            daily_pnl_pct: Daily P&L percentage
            positions: Current positions

        Returns:
            Discord embed dictionary
        """
        color = 0x00FF00 if daily_pnl >= 0 else 0xFF0000

        positions_text = "No positions" if not positions else "\n".join([
            f"• {p['symbol']}: {p['quantity']:.4f} @ ${p['current_price']:.2f}"
            for p in positions
        ])

        embed = {
            "title": f"📊 Daily Summary - {date}",
            "color": color,
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Portfolio Value",
                    "value": f"${portfolio_value:,.2f}",
                    "inline": True,
                },
                {
                    "name": "Daily P&L",
                    "value": f"${daily_pnl:+,.2f} ({daily_pnl_pct:+.2f}%)",
                    "inline": True,
                },
                {
                    "name": "Positions",
                    "value": positions_text,
                    "inline": False,
                },
            ],
        }

        return embed

    @staticmethod
    def signal_generated(
        signal_type: str,
        symbol: str,
        price: float,
        rsi: float,
        reason: str,
    ) -> dict:
        """
        Generate Discord embed for signal notification.

        Args:
            signal_type: BUY, SELL, or HOLD
            symbol: Stock symbol
            price: Current price
            rsi: Current RSI value
            reason: Signal reason

        Returns:
            Discord embed dictionary
        """
        colors = {
            "BUY": 0x00FF00,
            "SELL": 0xFF0000,
            "HOLD": 0x808080,
        }

        embed = {
            "title": f"🎯 Signal: {signal_type} {symbol}",
            "color": colors.get(signal_type, 0x808080),
            "timestamp": datetime.utcnow().isoformat(),
            "fields": [
                {
                    "name": "Price",
                    "value": f"${price:.2f}",
                    "inline": True,
                },
                {
                    "name": "RSI(2)",
                    "value": f"{rsi:.1f}",
                    "inline": True,
                },
                {
                    "name": "Reason",
                    "value": reason,
                    "inline": False,
                },
            ],
        }

        return embed
