#!/usr/bin/env python3
"""
Daily Report Sender
Sends daily trading summary to Discord after US market close.
"""
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytz
import requests

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from automation.bot_analytics import (
    calculate_daily_uptime,
    analyze_no_trade_reason,
    format_uptime_for_discord,
    format_no_trade_for_discord,
)
from config.settings import get_settings
from execution.broker import AlpacaBroker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")


def get_todays_trades(trades_file: str = "logs/trades.json") -> list[dict]:
    """Get trades from today (US Eastern time)."""
    today_et = datetime.now(ET).strftime("%Y-%m-%d")

    try:
        with open(trades_file, "r") as f:
            all_trades = json.load(f)

        todays = []
        for trade in all_trades:
            trade_date = trade.get("timestamp_utc", "")[:10]
            if trade_date == today_et:
                todays.append(trade)

        return todays
    except FileNotFoundError:
        return []
    except json.JSONDecodeError:
        return []


def calculate_daily_pnl(trades: list[dict]) -> tuple[float, int, int]:
    """Calculate daily P&L from trades."""
    total_pnl = 0.0
    wins = 0
    losses = 0

    for trade in trades:
        pnl = trade.get("realized_pnl_usd", 0) or 0
        total_pnl += pnl
        if pnl > 0:
            wins += 1
        elif pnl < 0:
            losses += 1

    return total_pnl, wins, losses


def create_daily_embed(
    date: str,
    equity: float,
    daily_pnl: float,
    daily_pnl_pct: float,
    trades: list[dict],
    wins: int,
    losses: int,
    position: dict | None,
    uptime_stats=None,
    no_trade_reason=None,
) -> dict:
    """Create Discord embed for daily report."""

    # Color based on P&L
    if daily_pnl > 0:
        color = 0x00FF00  # Green
    elif daily_pnl < 0:
        color = 0xFF0000  # Red
    else:
        color = 0x808080  # Gray

    # Trade summary
    total_trades = len(trades)
    if total_trades > 0:
        trade_summary = f"Total: {total_trades} | ✅ {wins} | ❌ {losses}"
    else:
        trade_summary = "No trades today"

    # Position info
    if position:
        pos_text = (
            f"**{position['symbol']}**: {position['quantity']:.4f} shares\n"
            f"Entry: ${position['avg_entry_price']:.2f}\n"
            f"Current: ${position['current_price']:.2f}\n"
            f"Unrealized: ${position['unrealized_pl']:+.2f} ({position['unrealized_plpc']*100:+.2f}%)"
        )
    else:
        pos_text = "No open positions"

    # Build embed
    embed = {
        "title": f"📊 Daily Report - {date}",
        "color": color,
        "timestamp": datetime.utcnow().isoformat(),
        "fields": [
            {
                "name": "💰 Portfolio Value",
                "value": f"**${equity:,.2f}**",
                "inline": True,
            },
            {
                "name": "📈 Daily P&L",
                "value": f"**${daily_pnl:+,.2f}** ({daily_pnl_pct:+.2f}%)",
                "inline": True,
            },
            {
                "name": "🔄 Today's Trades",
                "value": trade_summary,
                "inline": True,
            },
            {
                "name": "📦 Current Position",
                "value": pos_text,
                "inline": False,
            },
        ],
        "footer": {
            "text": "TQQQ RSI(2) Paper Trading",
        },
    }

    # Add individual trade details if any
    if trades:
        trade_details = []
        for t in trades[-5:]:  # Last 5 trades
            side = t.get("side", "?")
            qty = t.get("quantity", 0)
            price = t.get("fill_price", 0)
            pnl = t.get("realized_pnl_usd")

            if pnl is not None:
                trade_details.append(f"• {side} {qty:.2f} @ ${price:.2f} → ${pnl:+.2f}")
            else:
                trade_details.append(f"• {side} {qty:.2f} @ ${price:.2f}")

        embed["fields"].append({
            "name": "📝 Trade Details",
            "value": "\n".join(trade_details) or "None",
            "inline": False,
        })

    # Add bot uptime info
    if uptime_stats:
        uptime_emoji = "🟢" if uptime_stats.uptime_pct >= 95 else "🟡" if uptime_stats.uptime_pct >= 80 else "🔴"
        hours = uptime_stats.bot_running_minutes // 60
        mins = uptime_stats.bot_running_minutes % 60

        uptime_text = f"{uptime_emoji} **{uptime_stats.uptime_pct:.1f}%** ({hours}h {mins}m / 6.5h)"
        if uptime_stats.errors:
            uptime_text += f"\n⚠️ {len(uptime_stats.errors)} error(s)"

        embed["fields"].append({
            "name": "🤖 Bot Uptime",
            "value": uptime_text,
            "inline": True,
        })

    # Add no-trade reason if no trades today
    if not trades and no_trade_reason:
        reason_text = format_no_trade_for_discord(no_trade_reason)
        embed["fields"].append({
            "name": "❓ Why No Trades?",
            "value": reason_text,
            "inline": False,
        })

    return embed


def send_daily_report():
    """Generate and send daily report to Discord."""
    settings = get_settings()
    webhook_url = settings.discord.daily_webhook_url

    if not webhook_url:
        logger.error("Daily webhook URL not configured")
        return False

    # Get current date in ET
    now_et = datetime.now(ET)
    date_str = now_et.strftime("%Y-%m-%d (%a)")
    date_iso = now_et.strftime("%Y-%m-%d")

    logger.info(f"Generating daily report for {date_str}")

    try:
        # Get account info from Alpaca
        broker = AlpacaBroker(paper=True)
        account = broker.get_account()
        equity = account["equity"]

        # Get position
        position = broker.get_position("TQQQ")

        # Get today's trades
        trades = get_todays_trades()
        daily_pnl, wins, losses = calculate_daily_pnl(trades)

        # Calculate P&L percentage (assuming starting equity)
        # This is simplified - ideally track starting equity
        daily_pnl_pct = (daily_pnl / equity * 100) if equity > 0 else 0

        # Get bot uptime stats
        uptime_stats = calculate_daily_uptime(date=date_iso)
        logger.info(f"Bot uptime: {uptime_stats.uptime_pct:.1f}%")

        # Get no-trade reason if no trades
        no_trade_reason = None
        if not trades:
            no_trade_reason = analyze_no_trade_reason(date=date_iso)
            logger.info(f"No trade reason: {no_trade_reason.primary_reason}")

        # Create embed
        embed = create_daily_embed(
            date=date_str,
            equity=equity,
            daily_pnl=daily_pnl,
            daily_pnl_pct=daily_pnl_pct,
            trades=trades,
            wins=wins,
            losses=losses,
            position=position,
            uptime_stats=uptime_stats,
            no_trade_reason=no_trade_reason,
        )

        # Send to Discord
        response = requests.post(
            webhook_url,
            json={"embeds": [embed]},
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        response.raise_for_status()

        logger.info("Daily report sent successfully!")
        return True

    except Exception as e:
        logger.error(f"Failed to send daily report: {e}")
        return False


if __name__ == "__main__":
    success = send_daily_report()
    sys.exit(0 if success else 1)
