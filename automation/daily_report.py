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


def format_holding_time(minutes: int | None) -> str:
    """Format holding time in human readable format."""
    if minutes is None:
        return "N/A"
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def format_trade_time(timestamp_str: str) -> str:
    """Extract time from ISO timestamp in ET."""
    try:
        # Parse UTC timestamp
        if "T" in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            dt_et = dt.astimezone(ET)
            return dt_et.strftime("%H:%M")
    except Exception:
        pass
    return "??:??"


def format_detailed_trades(trades: list[dict], max_trades: int = 3) -> str:
    """
    Format trades with detailed review information.

    Groups BUY/SELL pairs and shows indicators, holding time, etc.
    """
    if not trades:
        return ""

    lines = []
    trade_num = 0

    # Process trades (show most recent first, limit to max_trades complete trades)
    processed = 0
    i = len(trades) - 1

    while i >= 0 and processed < max_trades:
        t = trades[i]
        side = t.get("side", "?")
        symbol = t.get("symbol", "TQQQ")
        qty = t.get("quantity", 0)
        fill_price = t.get("fill_price", 0)
        pnl = t.get("realized_pnl_usd")
        reason = t.get("signal_reason", "")
        rsi = t.get("rsi_value")
        vwap = t.get("vwap_value")
        slippage = t.get("slippage", 0)
        holding_mins = t.get("holding_minutes")
        entry_price = t.get("entry_price")
        entry_time = t.get("entry_time")
        day_range_pct = t.get("day_range_pct")
        timestamp = t.get("timestamp_utc", "")

        trade_num += 1

        # Format trade header
        if side == "SELL" and pnl is not None:
            # This is an exit trade with P&L
            pnl_pct = (pnl / (entry_price * qty) * 100) if entry_price and qty else 0
            pnl_emoji = "🟢" if pnl > 0 else "🔴" if pnl < 0 else "⚪"

            lines.append(f"**Trade #{trade_num}** {pnl_emoji} **${pnl:+.2f}** ({pnl_pct:+.1f}%)")
            lines.append("━━━━━━━━━━━━━━━━")

            # Entry info (if available)
            if entry_price and entry_time:
                entry_time_str = format_trade_time(entry_time)
                lines.append(f"📈 진입: ${entry_price:.2f} @ {entry_time_str} ET")

            # Exit info
            exit_time_str = format_trade_time(timestamp)
            exit_line = f"📉 청산: ${fill_price:.2f} @ {exit_time_str} ET"
            lines.append(exit_line)

            # Indicator at exit
            indicator_parts = []
            if rsi is not None:
                indicator_parts.append(f"RSI: {rsi:.1f}")
            if vwap is not None:
                indicator_parts.append(f"VWAP: ${vwap:.2f}")
            if indicator_parts:
                lines.append(f"   └ {' | '.join(indicator_parts)}")

            # Reason
            if reason:
                lines.append(f"   └ 사유: {reason}")

            # Holding time & slippage
            meta_parts = []
            if holding_mins is not None:
                meta_parts.append(f"보유: {format_holding_time(holding_mins)}")
            if slippage and abs(slippage) > 0.0001:
                meta_parts.append(f"슬리피지: {slippage*100:.2f}%")
            if day_range_pct is not None:
                meta_parts.append(f"일중위치: {day_range_pct:.0f}%")
            if meta_parts:
                lines.append(f"📊 {' | '.join(meta_parts)}")

            processed += 1

        elif side == "BUY":
            # Entry trade (no exit yet)
            lines.append(f"**Trade #{trade_num}** 📥 진입")
            lines.append("━━━━━━━━━━━━━━━━")

            time_str = format_trade_time(timestamp)
            lines.append(f"📈 매수: {qty:.2f} {symbol} @ ${fill_price:.2f} ({time_str} ET)")

            # Indicators at entry
            indicator_parts = []
            if rsi is not None:
                indicator_parts.append(f"RSI: {rsi:.1f}")
            if vwap is not None:
                indicator_parts.append(f"VWAP: ${vwap:.2f}")
            if indicator_parts:
                lines.append(f"   └ {' | '.join(indicator_parts)}")

            if reason:
                lines.append(f"   └ 사유: {reason}")

            if day_range_pct is not None:
                lines.append(f"📊 일중위치: {day_range_pct:.0f}% (저가=0%, 고가=100%)")

            processed += 1

        lines.append("")  # Empty line between trades
        i -= 1

    # Trim trailing empty lines
    while lines and lines[-1] == "":
        lines.pop()

    result = "\n".join(lines)

    # Discord embed field limit is 1024 chars
    if len(result) > 1000:
        result = result[:997] + "..."

    return result


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

    # Add detailed trade review if any trades
    if trades:
        # Group trades into entry/exit pairs for better review
        trade_blocks = format_detailed_trades(trades)

        if trade_blocks:
            embed["fields"].append({
                "name": "📝 Trade Details",
                "value": trade_blocks,
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
