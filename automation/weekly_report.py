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

from automation.bot_analytics import (
    calculate_weekly_uptime,
    analyze_no_trade_reason,
    format_uptime_for_discord,
)
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
            "avg_holding_mins": 0,
            "avg_slippage": 0,
            "best_trade_detail": None,
            "worst_trade_detail": None,
        }

    pnls = [t.get("realized_pnl_usd", 0) or 0 for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    # Calculate average holding time
    holding_times = [t.get("holding_minutes") for t in trades if t.get("holding_minutes") is not None]
    avg_holding = sum(holding_times) / len(holding_times) if holding_times else 0

    # Calculate average slippage
    slippages = [abs(t.get("slippage", 0) or 0) for t in trades]
    avg_slippage = sum(slippages) / len(slippages) if slippages else 0

    # Find best and worst trade details
    best_trade_detail = None
    worst_trade_detail = None

    if pnls:
        best_pnl = max(pnls)
        worst_pnl = min(pnls)

        for t in trades:
            pnl = t.get("realized_pnl_usd", 0) or 0
            if pnl == best_pnl and best_trade_detail is None:
                best_trade_detail = t
            if pnl == worst_pnl and worst_trade_detail is None:
                worst_trade_detail = t

    return {
        "total_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(trades) * 100 if trades else 0,
        "total_pnl": sum(pnls),
        "best_trade": max(pnls) if pnls else 0,
        "worst_trade": min(pnls) if pnls else 0,
        "avg_pnl": sum(pnls) / len(pnls) if pnls else 0,
        "avg_holding_mins": avg_holding,
        "avg_slippage": avg_slippage,
        "best_trade_detail": best_trade_detail,
        "worst_trade_detail": worst_trade_detail,
    }


def format_holding_time(minutes: float | None) -> str:
    """Format holding time in human readable format."""
    if minutes is None or minutes == 0:
        return "N/A"
    minutes = int(minutes)
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours}h {mins}m"


def format_trade_time(timestamp_str: str) -> str:
    """Extract time from ISO timestamp in ET."""
    try:
        if "T" in timestamp_str:
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
            dt_et = dt.astimezone(ET)
            return dt_et.strftime("%m/%d %H:%M")
    except Exception:
        pass
    return "??/?? ??:??"


def format_trade_summary(trade: dict | None, label: str) -> str:
    """Format a single trade for weekly summary."""
    if not trade:
        return f"{label}: N/A"

    pnl = trade.get("realized_pnl_usd", 0) or 0
    entry_price = trade.get("entry_price")
    fill_price = trade.get("fill_price", 0)
    rsi = trade.get("rsi_value")
    reason = trade.get("signal_reason", "")
    timestamp = trade.get("timestamp_utc", "")
    holding_mins = trade.get("holding_minutes")

    time_str = format_trade_time(timestamp)

    lines = [f"**{label}**: ${pnl:+.2f}"]

    detail_parts = []
    if entry_price:
        detail_parts.append(f"${entry_price:.2f}→${fill_price:.2f}")
    if rsi is not None:
        detail_parts.append(f"RSI:{rsi:.0f}")
    if holding_mins:
        detail_parts.append(format_holding_time(holding_mins))

    if detail_parts:
        lines.append(f"└ {' | '.join(detail_parts)}")

    if reason:
        lines.append(f"└ {reason[:30]}")

    return "\n".join(lines)


def create_weekly_embed(
    week_range: str,
    equity: float,
    stats: dict,
    position: dict | None,
    weekly_uptime: list = None,
    daily_reasons: list = None,
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
                "name": "📊 Avg P&L",
                "value": f"${stats['avg_pnl']:+.2f}",
                "inline": True,
            },
            {
                "name": "⏱️ Avg Holding",
                "value": format_holding_time(stats.get('avg_holding_mins', 0)),
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

    # Add best/worst trade details
    if stats.get("best_trade_detail") or stats.get("worst_trade_detail"):
        trade_review_lines = []

        if stats.get("best_trade_detail"):
            trade_review_lines.append(format_trade_summary(stats["best_trade_detail"], "🏆 Best"))

        if stats.get("worst_trade_detail"):
            trade_review_lines.append("")
            trade_review_lines.append(format_trade_summary(stats["worst_trade_detail"], "💔 Worst"))

        # Add average slippage if notable
        avg_slip = stats.get("avg_slippage", 0)
        if avg_slip > 0.001:  # > 0.1%
            trade_review_lines.append("")
            trade_review_lines.append(f"📉 평균 슬리피지: {avg_slip*100:.2f}%")

        embed["fields"].append({
            "name": "📝 Trade Review",
            "value": "\n".join(trade_review_lines),
            "inline": False,
        })

    # Add weekly uptime summary
    if weekly_uptime:
        total_market_mins = sum(u.market_minutes for u in weekly_uptime)
        total_running_mins = sum(u.bot_running_minutes for u in weekly_uptime)
        weekly_uptime_pct = (total_running_mins / total_market_mins * 100) if total_market_mins > 0 else 0

        uptime_emoji = "🟢" if weekly_uptime_pct >= 95 else "🟡" if weekly_uptime_pct >= 80 else "🔴"
        total_hours = total_running_mins // 60
        total_mins = total_running_mins % 60

        uptime_lines = [f"{uptime_emoji} **Weekly: {weekly_uptime_pct:.1f}%** ({total_hours}h {total_mins}m)"]
        for u in weekly_uptime:
            uptime_lines.append(format_uptime_for_discord(u))

        embed["fields"].append({
            "name": "🤖 Bot Uptime",
            "value": "\n".join(uptime_lines),
            "inline": False,
        })

    # Add no-trade day analysis
    if daily_reasons:
        no_trade_days = [r for r in daily_reasons if r.primary_reason != "Trades occurred" and r.market_condition != "closed"]
        if no_trade_days:
            reason_lines = []
            for reason in no_trade_days[:5]:  # Max 5 days
                if reason.rsi_value is not None:
                    reason_lines.append(f"• RSI={reason.rsi_value:.1f} ({reason.market_condition})")
                else:
                    reason_lines.append(f"• {reason.primary_reason[:50]}")

            if reason_lines:
                embed["fields"].append({
                    "name": f"❓ No-Trade Days ({len(no_trade_days)})",
                    "value": "\n".join(reason_lines),
                    "inline": False,
                })

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

        # Get weekly uptime stats
        weekly_uptime = calculate_weekly_uptime()
        if weekly_uptime:
            avg_uptime = sum(u.uptime_pct for u in weekly_uptime) / len(weekly_uptime)
            logger.info(f"Weekly avg uptime: {avg_uptime:.1f}%")

        # Get no-trade reasons for each day
        daily_reasons = []
        now_et = datetime.now(ET)
        days_since_monday = now_et.weekday()
        monday = now_et - timedelta(days=days_since_monday)

        for i in range(min(5, days_since_monday + 1)):  # Mon-Fri up to today
            day = monday + timedelta(days=i)
            reason = analyze_no_trade_reason(date=day.strftime("%Y-%m-%d"))
            daily_reasons.append(reason)

        # Create embed
        embed = create_weekly_embed(
            week_range=week_range,
            equity=equity,
            stats=stats,
            position=position,
            weekly_uptime=weekly_uptime,
            daily_reasons=daily_reasons,
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
