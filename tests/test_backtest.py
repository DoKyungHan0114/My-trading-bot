#!/usr/bin/env python3
"""
Simple test script to verify backtest engine works.
Run: python test_backtest.py
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_synthetic_backtest():
    """Test backtest with synthetic data."""
    print("=" * 60)
    print("TQQQ RSI(2) Mean Reversion - Backtest Test")
    print("=" * 60)
    print()

    # Test imports
    print("Testing imports...")
    try:
        from config.settings import get_settings
        from config.constants import SYMBOL, RSI_PERIOD, RSI_OVERSOLD, SMA_PERIOD
        print("  ✓ Config modules loaded")
    except ImportError as e:
        print(f"  ✗ Config import failed: {e}")
        return False

    try:
        from data.fetcher import DataFetcher
        from data.storage import DataStorage
        print("  ✓ Data modules loaded")
    except ImportError as e:
        print(f"  ✗ Data import failed: {e}")
        return False

    try:
        from strategy.indicators import calculate_rsi, calculate_sma, add_all_indicators
        from strategy.signals import SignalGenerator
        from strategy.risk_manager import RiskManager
        print("  ✓ Strategy modules loaded")
    except ImportError as e:
        print(f"  ✗ Strategy import failed: {e}")
        return False

    try:
        from execution.portfolio import Portfolio
        from execution.orders import Order
        print("  ✓ Execution modules loaded")
    except ImportError as e:
        print(f"  ✗ Execution import failed: {e}")
        return False

    try:
        from backtest.engine import BacktestEngine
        from backtest.metrics import MetricsCalculator
        print("  ✓ Backtest modules loaded")
    except ImportError as e:
        print(f"  ✗ Backtest import failed: {e}")
        return False

    try:
        from notifications.discord import DiscordNotifier
        print("  ✓ Notification modules loaded")
    except ImportError as e:
        print(f"  ✗ Notification import failed: {e}")
        return False

    print()
    print("Running backtest with synthetic data...")
    print()

    # Run backtest
    try:
        engine = BacktestEngine(initial_capital=10000.0)
        result = engine.run(
            start_date="2023-01-01",
            end_date="2024-12-31",
        )

        # Print results
        print(result.format_report())

        print()
        print("=" * 60)
        print("BACKTEST TEST COMPLETED SUCCESSFULLY!")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"Backtest failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_synthetic_backtest()
    sys.exit(0 if success else 1)
