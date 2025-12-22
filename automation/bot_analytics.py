"""
Bot Analytics Module
Calculates bot uptime and analyzes reasons for no trades.
"""
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytz

logger = logging.getLogger(__name__)

ET = pytz.timezone("America/New_York")

# Market hours in ET
MARKET_OPEN_HOUR = 9
MARKET_OPEN_MINUTE = 30
MARKET_CLOSE_HOUR = 16
MARKET_CLOSE_MINUTE = 0

# Total market minutes per day
MARKET_MINUTES_PER_DAY = (MARKET_CLOSE_HOUR * 60 + MARKET_CLOSE_MINUTE) - (
    MARKET_OPEN_HOUR * 60 + MARKET_OPEN_MINUTE
)  # 390 minutes


@dataclass
class UptimeStats:
    """Bot uptime statistics."""

    date: str
    market_minutes: int  # Total market minutes
    bot_running_minutes: int  # Minutes bot was running during market hours
    uptime_pct: float  # Percentage uptime
    start_events: int  # Number of bot starts
    stop_events: int  # Number of bot stops
    errors: list[str]  # List of errors encountered


@dataclass
class NoTradeReason:
    """Reason why no trade occurred."""

    primary_reason: str
    details: list[str]
    rsi_value: Optional[float] = None
    rsi_threshold: float = 30.0
    market_condition: str = "unknown"


def parse_log_timestamp(log_line: str, system_tz: str = "Australia/Brisbane") -> Optional[datetime]:
    """
    Parse timestamp from log line.

    Args:
        log_line: Log line with timestamp
        system_tz: System timezone (logs are in local time)

    Returns:
        Datetime in ET or None if parsing fails
    """
    # Pattern: 2025-12-22 23:07:14,676
    match = re.match(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", log_line)
    if not match:
        return None

    try:
        system_tz_obj = pytz.timezone(system_tz)
        dt = datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
        dt = system_tz_obj.localize(dt)
        return dt.astimezone(ET)
    except Exception:
        return None


def calculate_daily_uptime(
    log_file: str = "logs/trading.log",
    date: Optional[str] = None,
    system_tz: str = "Australia/Brisbane",
) -> UptimeStats:
    """
    Calculate bot uptime for a specific day.

    Args:
        log_file: Path to trading log file
        date: Date string (YYYY-MM-DD) in ET, defaults to today
        system_tz: System timezone for log timestamps

    Returns:
        UptimeStats for the day
    """
    if date is None:
        date = datetime.now(ET).strftime("%Y-%m-%d")

    target_date = datetime.strptime(date, "%Y-%m-%d")
    market_open = ET.localize(
        datetime(target_date.year, target_date.month, target_date.day,
                 MARKET_OPEN_HOUR, MARKET_OPEN_MINUTE)
    )
    market_close = ET.localize(
        datetime(target_date.year, target_date.month, target_date.day,
                 MARKET_CLOSE_HOUR, MARKET_CLOSE_MINUTE)
    )

    # Check if weekend
    if target_date.weekday() >= 5:
        return UptimeStats(
            date=date,
            market_minutes=0,
            bot_running_minutes=0,
            uptime_pct=0.0,
            start_events=0,
            stop_events=0,
            errors=["Weekend - market closed"],
        )

    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
    except FileNotFoundError:
        return UptimeStats(
            date=date,
            market_minutes=MARKET_MINUTES_PER_DAY,
            bot_running_minutes=0,
            uptime_pct=0.0,
            start_events=0,
            stop_events=0,
            errors=["Log file not found"],
        )

    # Track bot state
    bot_running = False
    last_start_time = None
    running_minutes = 0
    start_events = 0
    stop_events = 0
    errors = []

    for line in lines:
        timestamp = parse_log_timestamp(line, system_tz)
        if timestamp is None:
            continue

        # Only process lines from target date (in ET)
        if timestamp.strftime("%Y-%m-%d") != date:
            # But track state from before
            if "Starting TQQQ Trading Bot" in line:
                bot_running = True
                last_start_time = timestamp
            elif "Shutdown" in line or "stopped" in line.lower():
                bot_running = False
            continue

        # Track events during target date
        if "Starting TQQQ Trading Bot" in line:
            start_events += 1
            bot_running = True
            # Start counting from market open or start time, whichever is later
            last_start_time = max(timestamp, market_open)

        elif "Shutdown" in line or "Scheduler stopped" in line:
            stop_events += 1
            if bot_running and last_start_time:
                # Stop counting at market close or stop time, whichever is earlier
                stop_time = min(timestamp, market_close)
                if stop_time > last_start_time and last_start_time < market_close:
                    running_minutes += (stop_time - last_start_time).total_seconds() / 60
            bot_running = False
            last_start_time = None

        elif "[ERROR]" in line:
            # Extract error message
            error_match = re.search(r"\[ERROR\] (.+)", line)
            if error_match:
                error_msg = error_match.group(1)[:100]  # Truncate
                if error_msg not in errors:
                    errors.append(error_msg)

    # If bot is still running at market close
    if bot_running and last_start_time and last_start_time < market_close:
        end_time = min(datetime.now(ET), market_close)
        if end_time > last_start_time:
            running_minutes += (end_time - last_start_time).total_seconds() / 60

    # Calculate percentage
    uptime_pct = (running_minutes / MARKET_MINUTES_PER_DAY * 100) if MARKET_MINUTES_PER_DAY > 0 else 0
    uptime_pct = min(100.0, uptime_pct)  # Cap at 100%

    return UptimeStats(
        date=date,
        market_minutes=MARKET_MINUTES_PER_DAY,
        bot_running_minutes=int(running_minutes),
        uptime_pct=round(uptime_pct, 1),
        start_events=start_events,
        stop_events=stop_events,
        errors=errors[:5],  # Limit to 5 errors
    )


def calculate_weekly_uptime(
    log_file: str = "logs/trading.log",
    system_tz: str = "Australia/Brisbane",
) -> list[UptimeStats]:
    """
    Calculate bot uptime for the current week.

    Returns:
        List of UptimeStats for each trading day
    """
    now_et = datetime.now(ET)

    # Find Monday of this week
    days_since_monday = now_et.weekday()
    monday = now_et - timedelta(days=days_since_monday)

    weekly_stats = []
    for i in range(5):  # Mon-Fri
        day = monday + timedelta(days=i)
        if day.date() <= now_et.date():  # Only past and today
            stats = calculate_daily_uptime(log_file, day.strftime("%Y-%m-%d"), system_tz)
            weekly_stats.append(stats)

    return weekly_stats


def analyze_no_trade_reason(
    date: Optional[str] = None,
    trades_file: str = "logs/trades.json",
    reports_dir: str = "reports",
) -> NoTradeReason:
    """
    Analyze why no trades occurred on a given day.

    Args:
        date: Date string (YYYY-MM-DD) in ET, defaults to today
        trades_file: Path to trades JSON file
        reports_dir: Directory containing analysis reports

    Returns:
        NoTradeReason with explanation
    """
    if date is None:
        date = datetime.now(ET).strftime("%Y-%m-%d")

    target_date = datetime.strptime(date, "%Y-%m-%d")
    details = []
    rsi_value = None
    market_condition = "unknown"

    # Check if weekend
    if target_date.weekday() >= 5:
        return NoTradeReason(
            primary_reason="Weekend - market closed",
            details=["No trading on weekends"],
            market_condition="closed",
        )

    # Check if there were trades
    try:
        with open(trades_file, "r") as f:
            all_trades = json.load(f)

        todays_trades = [
            t for t in all_trades
            if t.get("timestamp_utc", "")[:10] == date
        ]

        if todays_trades:
            return NoTradeReason(
                primary_reason="Trades occurred",
                details=[f"{len(todays_trades)} trade(s) executed"],
                market_condition="active",
            )
    except (FileNotFoundError, json.JSONDecodeError):
        details.append("Trade log not accessible")

    # Look for analysis reports from the day
    reports_path = Path(reports_dir)
    date_pattern = date.replace("-", "")

    latest_report = None
    try:
        report_files = sorted(reports_path.glob(f"analysis_{date_pattern}*.json"), reverse=True)
        if report_files:
            with open(report_files[0], "r") as f:
                latest_report = json.load(f)
    except Exception as e:
        details.append(f"Report not accessible: {e}")

    if latest_report:
        market = latest_report.get("market_condition", {})
        strategy = latest_report.get("strategy", {})

        rsi_value = market.get("rsi")
        rsi_threshold = strategy.get("rsi_oversold", 30)
        current_price = market.get("current_price", 0)
        vwap = market.get("vwap", 0)
        bb_lower = market.get("bb_lower", 0)
        daily_change = market.get("daily_change_pct", 0)

        # Determine market condition
        if daily_change > 1:
            market_condition = "bullish"
        elif daily_change < -1:
            market_condition = "bearish"
        else:
            market_condition = "neutral"

        # Analyze why no entry signal
        reasons = []

        if rsi_value is not None:
            if rsi_value > rsi_threshold:
                gap = rsi_value - rsi_threshold
                reasons.append(f"RSI({rsi_value:.1f}) > threshold({rsi_threshold}) by {gap:.1f} points")
                if rsi_value > 70:
                    reasons.append("Market in overbought territory")

        # Check VWAP filter
        if strategy.get("vwap_filter_enabled") and strategy.get("vwap_entry_below"):
            if current_price > vwap > 0:
                reasons.append(f"Price(${current_price:.2f}) above VWAP(${vwap:.2f})")

        # Check BB filter
        if strategy.get("bb_filter_enabled"):
            if current_price > bb_lower > 0:
                reasons.append(f"Price above BB lower band(${bb_lower:.2f})")

        if reasons:
            primary = reasons[0]
            details.extend(reasons)
        else:
            primary = "No clear reason found"
            details.append("Check log files for more details")

        return NoTradeReason(
            primary_reason=primary,
            details=details,
            rsi_value=rsi_value,
            rsi_threshold=rsi_threshold,
            market_condition=market_condition,
        )

    # No report found - generic response
    return NoTradeReason(
        primary_reason="No analysis data available",
        details=["Analysis report not found for this date"] + details,
        market_condition=market_condition,
    )


def format_uptime_for_discord(stats: UptimeStats) -> str:
    """Format uptime stats for Discord message."""
    if stats.market_minutes == 0:
        return f"📅 **{stats.date}**: Weekend (closed)"

    # Uptime emoji
    if stats.uptime_pct >= 95:
        emoji = "🟢"
    elif stats.uptime_pct >= 80:
        emoji = "🟡"
    elif stats.uptime_pct >= 50:
        emoji = "🟠"
    else:
        emoji = "🔴"

    hours = stats.bot_running_minutes // 60
    mins = stats.bot_running_minutes % 60

    text = f"{emoji} **{stats.date}**: {stats.uptime_pct:.1f}% ({hours}h {mins}m)"

    if stats.errors:
        text += f" | ⚠️ {len(stats.errors)} error(s)"

    return text


def format_no_trade_for_discord(reason: NoTradeReason) -> str:
    """Format no-trade reason for Discord message."""
    if reason.market_condition == "closed":
        return "📅 Market closed"

    if reason.primary_reason == "Trades occurred":
        return f"✅ {reason.details[0]}"

    # No trade emoji based on condition
    if reason.market_condition == "bullish":
        emoji = "📈"
    elif reason.market_condition == "bearish":
        emoji = "📉"
    else:
        emoji = "➖"

    text = f"{emoji} **{reason.primary_reason}**"

    if reason.rsi_value is not None:
        text += f"\n   RSI: {reason.rsi_value:.1f} (need ≤{reason.rsi_threshold:.0f} to buy)"

    for detail in reason.details[1:3]:  # Max 2 extra details
        text += f"\n   • {detail}"

    return text
