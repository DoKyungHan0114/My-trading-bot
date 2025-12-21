#!/usr/bin/env python3
"""
Weekly Report Sender
Sends weekly trading summary to Discord every Friday after US market close.
"""
import json
import logging
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytz
import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import get_settings
from execution.broker import AlpacaBroker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def get_week_range() -> tuple[str, str]:
    """Get current week's date range (Monday to Friday ET)."""
    now_et = datetime.now(ET)

    # Find this week's Monday
    days_since_monday = now_et.weekday()
    monday = now_et - timedelta(days=days_since_monday)
    friday = monday + timedelta(days=4)

    return monday.strftime("%Y-%m-%d"), friday.strftime("%Y-%m-%d")


def get_weeks_trades(trades_file: str = "logs/trades.json") -> list[dict]:
    """Get trades from this week."""
    start_date, end_date = get_week_range()

    try:
        with open(trades_file, "r") as f:
            all_trades = json.load(f)

        weeks_trades = []
        for trade in all_trades:
            trade_date = trade.get("timestamp_utc", "")[:10]
            if start_date <= trade_date <= end_date:
                weeks_trades.append(trade)

        return weeks_trades
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def calculate_weekly_stats(trades: list[dict]) -> dict:
    """Calculate weekly statistics from trades."""
    if not trades:
        return {
            "total_trades": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0,
            "total_pnl": 0,
            "best_trade": 0,
            "worst_trade": 0,
            "avg_pnl": 0,
        }

    pnls = [t.get("realized_pnl_usd", 0) or 0 for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0,
        "total_pnl": sum(pnls),
        "best_trade": max(pnls) if pnls else 0,
        "worst_trade": min(pnls) if pnls else 0,
        "avg_pnl": sum(pnls) / len(pnls) if pnls else 0,
    }


def create_weekly_embed(
    week_range: str,
    equity: float,
    stats: dict,
    position: dict | None,
) -> dict:
    """Create Discord embed for weekly report."""

    total_pnl = stats["total_pnl"]

    # Color based on weekly P&L
    if total_pnl > 0:
        color = 0x00FF00  # Green
    elif total_pnl < 0:
        color = 0xFF0000  # Red
    else:
        color = 0x808080  # Gray

    # Performance emoji
    if stats["win_rate"] >= 60:
        perf_emoji = "🔥"
    elif stats["win_rate"] >= 40:
        perf_emoji = "📊"
    else:
        perf_emoji = "📉"

    # Position info
    if position:
        pos_text = (
            f"**{position['symbol']}**: {position['quantity']:.4f} shares\n"
            f"Unrealized: ${position['unrealized_pl']:+.2f}"
        )
    else:
        pos_text = "No open positions"

    # Build embed
    embed = {
        "title": f"📅 Weekly Report - {week_range}",
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fields": [
            {
                "name": "💰 Portfolio Value",
                "value": f"**${equity:,.2f}**",
                "inline": True,
            },
            {
                "name": "📈 Weekly P&L",
                "value": f"**${total_pnl:+,.2f}**",
                "inline": True,
            },
            {
                "name": f"{perf_emoji} Win Rate",
                "value": f"**{stats['win_rate']:.1f}%**",
                "inline": True,
            },
            {
                "name": "🔄 Total Trades",
                "value": f"{stats['total_trades']} (✅ {stats['wins']} / ❌ {stats['losses']})",
                "inline": True,
            },
            {
                "name": "🏆 Best Trade",
                "value": f"${stats['best_trade']:+.2f}",
                "inline": True,
            },
            {
                "name": "💔 Worst Trade",
                "value": f"${stats['worst_trade']:+.2f}",
                "inline": True,
            },
            {
                "name": "📊 Avg P&L per Trade",
                "value": f"${stats['avg_pnl']:+.2f}",
                "inline": True,
            },
            {
                "name": "📦 Current Position",
                "value": pos_text,
                "inline": False,
            },
        ],
        "footer": {
            "text": "TQQQ RSI(2) Paper Trading | Weekly Summary",
        },
    }

    return embed


def send_weekly_report():
    """Generate and send weekly report to Discord."""
    settings = get_settings()
    webhook_url = settings.discord.weekly_webhook_url

    if not webhook_url:
        logger.error("Weekly webhook URL not configured")
        return False

    start_date, end_date = get_week_range()
    week_range = f"{start_date} ~ {end_date}"

    logger.info(f"Generating weekly report for {week_range}")

    try:
        # Get account info from Alpaca
        broker = AlpacaBroker(paper=True)
        account = broker.get_account()
        equity = account["equity"]

        # Get position
        position = broker.get_position("TQQQ")

        # Get this week's trades
        trades = get_weeks_trades()
        stats = calculate_weekly_stats(trades)

        # Create embed
        embed = create_weekly_embed(
            week_range=week_range,
            equity=equity,
            stats=stats,
            position=position,
        )

        # Send to Discord
        response = requests.post(
            webhook_url,
            json={"embeds": [embed]},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()

        logger.info("Weekly report sent successfully!")
        return True

    except Exception as e:
        logger.error(f"Failed to send weekly report: {e}")
        return False


if __name__ == "__main__":
    success = send_weekly_report()
    sys.exit(0 if success else 1)
