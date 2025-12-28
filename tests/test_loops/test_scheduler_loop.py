"""
Tests for AutomationScheduler loop safety.
"""
import sys
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

ET = pytz.timezone("America/New_York")


class TestSchedulerLoopSafety:
    """Test AutomationScheduler loop safety and exit conditions."""

    def test_scheduler_stops_on_stop_call(self, mock_scheduler):
        """Verify scheduler stops when stop() is called."""
        scheduler = mock_scheduler

        def run_scheduler():
            scheduler.run_loop()

        thread = threading.Thread(target=run_scheduler)
        thread.start()

        # Give it time to start
        time.sleep(0.3)

        # Stop the scheduler
        scheduler.stop()

        # Wait for thread to finish
        thread.join(timeout=5.0)

        assert not thread.is_alive(), "Scheduler did not stop within timeout"
        assert scheduler._running == False

    def test_stop_method_sets_running_false(self, mock_scheduler):
        """Verify stop() method sets _running to False."""
        scheduler = mock_scheduler
        scheduler._running = True

        scheduler.stop()

        assert scheduler._running == False


class TestSchedulerMarketHours:
    """Test market hours detection."""

    def test_is_market_hours_true_during_market(self, mock_scheduler):
        """Verify market hours detection during trading hours."""
        scheduler = mock_scheduler

        # Monday at noon ET
        market_time = ET.localize(datetime(2024, 12, 23, 12, 0))
        assert scheduler.is_market_hours(market_time) == True

    def test_is_market_hours_false_before_open(self, mock_scheduler):
        """Verify pre-market detection."""
        scheduler = mock_scheduler

        # Monday 8 AM ET (before 9:30)
        pre_market = ET.localize(datetime(2024, 12, 23, 8, 0))
        assert scheduler.is_market_hours(pre_market) == False

    def test_is_market_hours_false_after_close(self, mock_scheduler):
        """Verify post-market detection."""
        scheduler = mock_scheduler

        # Monday 5 PM ET (after 4:00)
        post_market = ET.localize(datetime(2024, 12, 23, 17, 0))
        assert scheduler.is_market_hours(post_market) == False

    def test_is_market_hours_false_on_weekend(self, mock_scheduler):
        """Verify weekend detection."""
        scheduler = mock_scheduler

        # Saturday at noon
        weekend = ET.localize(datetime(2024, 12, 28, 12, 0))
        assert scheduler.is_market_hours(weekend) == False

    def test_is_market_hours_at_market_open(self, mock_scheduler):
        """Verify exactly at market open."""
        scheduler = mock_scheduler

        # Monday 9:30 AM ET
        market_open = ET.localize(datetime(2024, 12, 23, 9, 30))
        assert scheduler.is_market_hours(market_open) == True

    def test_is_market_hours_at_market_close(self, mock_scheduler):
        """Verify exactly at market close."""
        scheduler = mock_scheduler

        # Monday 4:00 PM ET
        market_close = ET.localize(datetime(2024, 12, 23, 16, 0))
        assert scheduler.is_market_hours(market_close) == True


class TestSchedulerNextRunTime:
    """Test next run time calculation."""

    def test_get_next_run_time_returns_valid_time(self, mock_scheduler):
        """Verify next run time calculation."""
        scheduler = mock_scheduler

        # Monday 9 AM - before first analysis time
        test_time = ET.localize(datetime(2024, 12, 23, 9, 0))
        next_run = scheduler.get_next_run_time(after=test_time)

        assert next_run is not None
        assert next_run.hour == 11
        assert next_run.minute == 0

    def test_get_next_run_time_skips_past_times(self, mock_scheduler):
        """Verify skips times that have already passed."""
        scheduler = mock_scheduler

        # Monday noon - after 11:00 analysis
        test_time = ET.localize(datetime(2024, 12, 23, 12, 0))
        next_run = scheduler.get_next_run_time(after=test_time)

        assert next_run is not None
        assert next_run.hour == 14
        assert next_run.minute == 30

    def test_get_next_run_time_skips_weekends(self, mock_scheduler):
        """Verify next run time skips weekends."""
        scheduler = mock_scheduler

        # Friday 5 PM (after all analysis times)
        friday_evening = ET.localize(datetime(2024, 12, 27, 17, 0))
        next_run = scheduler.get_next_run_time(after=friday_evening)

        assert next_run is not None
        # Should be Monday (weekday 0)
        assert next_run.weekday() == 0

    def test_get_next_run_time_from_saturday(self, mock_scheduler):
        """Verify next run from Saturday goes to Monday."""
        scheduler = mock_scheduler

        # Saturday at noon
        saturday = ET.localize(datetime(2024, 12, 28, 12, 0))
        next_run = scheduler.get_next_run_time(after=saturday)

        assert next_run is not None
        assert next_run.weekday() == 0  # Monday


class TestSchedulerAnalysisTimeout:
    """Test scheduler analysis timeout handling."""

    def test_run_analysis_returns_none_on_dry_run(self, mock_scheduler):
        """Verify dry run mode skips Claude analysis."""
        scheduler = mock_scheduler
        scheduler.config.dry_run = True

        # Mock report generator
        mock_report = Mock()
        scheduler.report_gen.generate_report = Mock(return_value=mock_report)
        scheduler.report_gen.save_report = Mock(return_value="/tmp/test_report.json")

        result = scheduler.run_analysis()

        # Should return None in dry run mode
        assert result is None

    def test_run_analysis_handles_exception(self, mock_scheduler):
        """Verify analysis handles exceptions gracefully."""
        scheduler = mock_scheduler
        scheduler.config.dry_run = False

        # Make report generation fail
        scheduler.report_gen.generate_report = Mock(side_effect=Exception("Report generation failed"))

        result = scheduler.run_analysis()

        # Should return None on error
        assert result is None


class TestSchedulerRunLoop:
    """Test scheduler run loop behavior."""

    def test_run_loop_sleeps_between_checks(self, mock_scheduler):
        """Verify loop sleeps between run time checks (not spinning CPU)."""
        scheduler = mock_scheduler

        sleep_calls = []

        def track_sleep(seconds):
            sleep_calls.append(seconds)
            if len(sleep_calls) >= 3:
                scheduler.stop()

        # Mock get_next_run_time to return a time in the future
        future_time = datetime.now(ET) + timedelta(hours=1)
        scheduler.get_next_run_time = Mock(return_value=future_time)

        with patch("time.sleep", side_effect=track_sleep):
            scheduler.run_loop()

        # Should have slept multiple times (60 seconds each for chunk sleeping)
        assert len(sleep_calls) >= 1, "Scheduler should sleep while waiting"

    def test_run_loop_checks_market_hours(self, mock_scheduler):
        """Verify loop checks market hours before running analysis."""
        scheduler = mock_scheduler

        # Mock to return a past time (should trigger immediate run)
        past_time = datetime.now(ET) - timedelta(minutes=1)
        scheduler.get_next_run_time = Mock(return_value=past_time)

        # Mock market hours to return False
        scheduler.is_market_hours = Mock(return_value=False)

        run_analysis_called = [False]
        original_run_analysis = scheduler.run_analysis

        def tracked_run_analysis():
            run_analysis_called[0] = True
            return None

        scheduler.run_analysis = tracked_run_analysis

        call_count = [0]

        def stop_after_few(seconds):
            call_count[0] += 1
            if call_count[0] >= 2:
                scheduler.stop()

        with patch("time.sleep", side_effect=stop_after_few):
            scheduler.run_loop()

        # Should NOT have run analysis since market is closed
        assert run_analysis_called[0] == False
