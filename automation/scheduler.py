"""
Automation scheduler for intraday analysis.
Runs Claude analysis at configured intervals during market hours.
"""
import logging
import os
import signal
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional

import pytz

from automation.claude_analyzer import ClaudeAnalyzer, AnalysisResult
from database.firestore import FirestoreClient
from notifications.discord import DiscordNotifier
from reports.report_generator import ReportGenerator

logger = logging.getLogger(__name__)

# US Eastern timezone for market hours
ET = pytz.timezone("America/New_York")

# Market hours (ET)
MARKET_OPEN = 9  # 9:30 AM ET
MARKET_CLOSE = 16  # 4:00 PM ET


@dataclass
class ScheduleConfig:
    """Scheduler configuration."""

    # Analysis times in ET (24h format)
    analysis_times: list[tuple[int, int]]  # [(hour, minute), ...]
    # Auto-apply modifications
    auto_apply: bool = False
    # Minimum confidence for auto-apply
    min_confidence: float = 0.5
    # Run on weekends
    run_weekends: bool = False
    # Dry run mode (no actual changes)
    dry_run: bool = False


DEFAULT_SCHEDULE = ScheduleConfig(
    # Run at market open (9:00 AM) and market close (4:30 PM) ET
    analysis_times=[(9, 0), (16, 30)],
    auto_apply=False,
    min_confidence=0.5,
)


class AutomationScheduler:
    """Schedule and run automated analysis."""

    def __init__(
        self,
        config: Optional[ScheduleConfig] = None,
        firestore_client: Optional[FirestoreClient] = None,
    ):
        """
        Initialize scheduler.

        Args:
            config: Schedule configuration
            firestore_client: Firestore client instance
        """
        self.config = config or DEFAULT_SCHEDULE
        self.firestore = firestore_client
        self.report_gen = ReportGenerator()
        self.analyzer = ClaudeAnalyzer(
            firestore_client=firestore_client,
            report_generator=self.report_gen,
        )
        self.discord = DiscordNotifier()
        self._running = False
        self._last_run: Optional[datetime] = None

    def is_market_hours(self, dt: Optional[datetime] = None) -> bool:
        """
        Check if current time is during market hours.

        Args:
            dt: Datetime to check (uses now if None)

        Returns:
            True if during market hours
        """
        if dt is None:
            dt = datetime.now(ET)
        elif dt.tzinfo is None:
            dt = ET.localize(dt)
        else:
            dt = dt.astimezone(ET)

        # Check weekday (0=Monday, 6=Sunday)
        if dt.weekday() >= 5 and not self.config.run_weekends:
            return False

        # Check hours
        hour = dt.hour
        minute = dt.minute
        time_val = hour * 60 + minute

        market_open = MARKET_OPEN * 60 + 30  # 9:30 AM
        market_close = MARKET_CLOSE * 60  # 4:00 PM

        return market_open <= time_val <= market_close

    def get_next_run_time(self, after: Optional[datetime] = None) -> Optional[datetime]:
        """
        Calculate next scheduled run time.

        Args:
            after: Start time (uses now if None)

        Returns:
            Next scheduled datetime or None if no more today
        """
        if after is None:
            after = datetime.now(ET)
        elif after.tzinfo is None:
            after = ET.localize(after)
        else:
            after = after.astimezone(ET)

        today = after.date()
        current_time = after.hour * 60 + after.minute

        # Find next scheduled time today
        for hour, minute in sorted(self.config.analysis_times):
            scheduled_time = hour * 60 + minute
            if scheduled_time > current_time:
                next_run = ET.localize(
                    datetime(today.year, today.month, today.day, hour, minute)
                )
                # Verify it's during market hours
                if self.is_market_hours(next_run):
                    return next_run

        # No more runs today, find next trading day
        next_day = after + timedelta(days=1)
        while next_day.weekday() >= 5 and not self.config.run_weekends:
            next_day += timedelta(days=1)

        # Return first scheduled time of next trading day
        if self.config.analysis_times:
            hour, minute = min(self.config.analysis_times)
            return ET.localize(
                datetime(
                    next_day.year,
                    next_day.month,
                    next_day.day,
                    hour,
                    minute,
                )
            )

        return None

    def _get_analysis_purpose(self) -> tuple[str, str]:
        """
        Determine analysis purpose based on current time.

        Returns:
            Tuple of (purpose, emoji)
        """
        now = datetime.now(ET)
        hour = now.hour

        if hour < 10:
            return "Pre-Market Check", "🌅"
        elif hour >= 16:
            return "Post-Market Analysis", "🌆"
        else:
            return "Intraday Check", "☀️"

    def run_analysis(self) -> Optional[AnalysisResult]:
        """
        Run a single analysis cycle.

        Returns:
            Analysis result or None on error
        """
        purpose, emoji = self._get_analysis_purpose()

        logger.info("=" * 60)
        logger.info(f"Starting {purpose}")
        logger.info(f"Time: {datetime.now(ET).strftime('%Y-%m-%d %H:%M:%S %Z')}")
        logger.info("=" * 60)

        # Discord: Analysis starting
        if self.discord.enabled:
            self.discord.send_message(
                f"{emoji} **{purpose} Started**\n"
                f"Time: {datetime.now(ET).strftime('%Y-%m-%d %H:%M ET')}"
            )

        try:
            # Generate report
            report = self.report_gen.generate_report()
            report_path = self.report_gen.save_report(report)
            logger.info(f"Report saved: {report_path}")

            # Run Claude analysis
            if self.config.dry_run:
                logger.info("DRY RUN - Skipping Claude analysis")
                return None

            result = self.analyzer.analyze(
                report=report,
                auto_apply=self.config.auto_apply,
                min_confidence=self.config.min_confidence,
            )

            if result:
                logger.info(f"Analysis complete: {result.summary}")

                # Discord: Send analysis result
                if self.discord.enabled:
                    mods_text = ""
                    if result.modifications:
                        mods_text = "\n**Modifications:**\n"
                        for mod in result.modifications:
                            mods_text += f"• `{mod.parameter}`: {mod.old_value} → {mod.new_value}\n"
                    else:
                        mods_text = "\n_No parameter changes suggested_"

                    applied_text = ""
                    if self.config.auto_apply and result.modifications:
                        if result.confidence >= self.config.min_confidence:
                            applied_text = "\n✅ **Changes Applied**"
                        else:
                            applied_text = f"\n⏸️ _Confidence {result.confidence:.0%} below threshold {self.config.min_confidence:.0%}_"

                    self.discord.send_message(
                        f"{emoji} **{purpose} Complete**\n"
                        f"**Summary:** {result.summary}\n"
                        f"**Confidence:** {result.confidence:.0%}"
                        f"{mods_text}{applied_text}"
                    )

                # Log session to Firestore if available
                if self.firestore and report.recent_performance:
                    perf = report.recent_performance
                    active = self.firestore.get_active_strategy()
                    if active:
                        self.firestore.create_session(
                            strategy_id=active["strategy_id"],
                            date=datetime.utcnow(),
                            total_pnl=perf.get("total_pnl", 0),
                            win_rate=perf.get("win_rate", 0),
                            max_drawdown=perf.get("max_drawdown", 0),
                            sharpe_ratio=0,  # Not in report
                            trade_count=perf.get("total_trades", 0),
                        )

            self._last_run = datetime.now(ET)
            return result

        except Exception as e:
            logger.error(f"Analysis failed: {e}", exc_info=True)
            # Discord: Send error notification
            if self.discord.enabled:
                self.discord.send_error_alert(
                    error_type="Analysis Failed",
                    message=str(e),
                    context=f"{purpose} at {datetime.now(ET).strftime('%H:%M ET')}",
                )
            return None

    def run_once(self) -> Optional[AnalysisResult]:
        """
        Run analysis once and exit.

        Returns:
            Analysis result
        """
        return self.run_analysis()

    def run_loop(self, on_complete: Optional[Callable] = None):
        """
        Run continuous scheduling loop.

        Args:
            on_complete: Callback after each analysis
        """
        self._running = True

        # Setup signal handlers
        def signal_handler(signum, frame):
            logger.info("Shutdown signal received")
            self._running = False

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        logger.info("Starting automation scheduler")
        logger.info(f"Analysis times: {self.config.analysis_times}")
        logger.info(f"Auto-apply: {self.config.auto_apply}")
        logger.info(f"Min confidence: {self.config.min_confidence:.0%}")

        # Discord start notification
        if self.discord.enabled:
            times_str = ", ".join([f"{h}:{m:02d} ET" for h, m in self.config.analysis_times])
            self.discord.send_message(
                f"**Claude Strategy Scheduler Started**\n"
                f"Analysis times: {times_str}\n"
                f"Auto-apply: {'Yes' if self.config.auto_apply else 'No'}"
            )

        while self._running:
            now = datetime.now(ET)
            next_run = self.get_next_run_time(now)

            if next_run is None:
                logger.info("No more runs scheduled, waiting for next trading day")
                time.sleep(3600)  # Sleep 1 hour
                continue

            wait_seconds = (next_run - now).total_seconds()

            if wait_seconds > 0:
                logger.info(f"Next run: {next_run.strftime('%Y-%m-%d %H:%M %Z')}")
                logger.info(f"Waiting {wait_seconds / 60:.1f} minutes...")

                # Sleep in chunks to allow signal handling
                while wait_seconds > 0 and self._running:
                    sleep_time = min(60, wait_seconds)
                    time.sleep(sleep_time)
                    wait_seconds -= sleep_time

            if not self._running:
                break

            # Check if we should actually run (might have drifted)
            if self.is_market_hours():
                result = self.run_analysis()
                if on_complete:
                    on_complete(result)
            else:
                logger.info("Outside market hours, skipping")

            # Small delay to prevent double-runs
            time.sleep(60)

        logger.info("Scheduler stopped")

        # Discord stop notification
        if self.discord.enabled:
            self.discord.send_message("**Claude Strategy Scheduler Stopped**")

    def stop(self):
        """Stop the scheduling loop."""
        self._running = False


def run_scheduler(
    auto_apply: bool = False,
    dry_run: bool = False,
    once: bool = False,
):
    """
    Run the automation scheduler.

    Args:
        auto_apply: Auto-apply strategy modifications
        dry_run: Run without making changes
        once: Run once and exit
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    config = ScheduleConfig(
        analysis_times=[(9, 0), (16, 30)],  # Market open & close
        auto_apply=auto_apply,
        min_confidence=0.5,
        dry_run=dry_run,
    )

    try:
        firestore = FirestoreClient()
        logger.info("Firestore connected")
    except Exception as e:
        logger.warning(f"Firestore not available: {e}")
        firestore = None

    scheduler = AutomationScheduler(config=config, firestore_client=firestore)

    if once:
        result = scheduler.run_once()
        if result:
            print(f"\nResult: {result.summary}")
    else:
        scheduler.run_loop()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run automation scheduler")
    parser.add_argument("--auto", action="store_true", help="Auto-apply modifications")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode")
    parser.add_argument("--once", action="store_true", help="Run once and exit")

    args = parser.parse_args()

    run_scheduler(
        auto_apply=args.auto,
        dry_run=args.dry_run,
        once=args.once,
    )
