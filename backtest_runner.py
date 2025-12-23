#!/usr/bin/env python3
"""
Backtest runner for RSI(2) TQQQ Mean Reversion Strategy.

Usage:
    python backtest_runner.py [--start START_DATE] [--end END_DATE] [--capital CAPITAL]
    python backtest_runner.py --optimize
    python backtest_runner.py --plot
    python backtest_runner.py --pdf --db  # Generate PDF and save to Firestore
"""
import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

from config.settings import get_settings, REPORTS_DIR
from backtest.engine import BacktestEngine
from backtest.optimizer import StrategyOptimizer
from notifications.discord import DiscordNotifier

# Optional imports
try:
    from reports.pdf_generator import PDFReportGenerator
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False

try:
    from database.firestore import FirestoreClient
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "logs" / "backtest.log"),
    ],
)
logger = logging.getLogger(__name__)


def run_backtest(
    start_date: str,
    end_date: str,
    initial_capital: float,
    save_results: bool = True,
    send_discord: bool = False,
    plot: bool = False,
    generate_pdf: bool = False,
    save_to_db: bool = False,
) -> dict:
    """
    Run a single backtest.

    Args:
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)
        initial_capital: Starting capital
        save_results: Save results to file
        send_discord: Send results to Discord
        plot: Generate plots
        generate_pdf: Generate PDF report
        save_to_db: Save results to Firestore

    Returns:
        Backtest results dictionary
    """
    logger.info("=" * 60)
    logger.info("TQQQ RSI(2) Mean Reversion Backtest")
    logger.info("=" * 60)

    # Load active strategy from Firestore (if available)
    strategy_id = None
    firestore_client = None
    if FIRESTORE_AVAILABLE:
        try:
            firestore_client = FirestoreClient()
            active_strategy = firestore_client.get_active_strategy()
            if active_strategy:
                strategy_id = active_strategy["strategy_id"]
                params = active_strategy.get("parameters", {})
                settings = get_settings()

                # Override settings with Firestore values
                settings.strategy.rsi_oversold = params.get("rsi_oversold", settings.strategy.rsi_oversold)
                settings.strategy.rsi_overbought = params.get("rsi_overbought", settings.strategy.rsi_overbought)
                settings.strategy.stop_loss_pct = params.get("stop_loss_pct", settings.strategy.stop_loss_pct)
                settings.strategy.position_size_pct = params.get("position_size_pct", settings.strategy.position_size_pct)
                settings.strategy.sma_period = params.get("sma_period", settings.strategy.sma_period)

                logger.info(f"Loaded strategy from Firestore: {strategy_id}")
                logger.info(f"  rsi_oversold: {settings.strategy.rsi_oversold}")
                logger.info(f"  rsi_overbought: {settings.strategy.rsi_overbought}")
                logger.info(f"  stop_loss_pct: {settings.strategy.stop_loss_pct}")
                logger.info(f"  position_size_pct: {settings.strategy.position_size_pct}")
        except Exception as e:
            logger.warning(f"Could not load strategy from Firestore: {e}")

    # Initialize engine
    engine = BacktestEngine(initial_capital=initial_capital)

    # Run backtest
    result = engine.run(start_date=start_date, end_date=end_date)

    # Print report
    print("\n" + result.format_report())

    # Save results to JSON
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if save_results:
        results_file = REPORTS_DIR / f"backtest_{timestamp}.json"
        with open(results_file, "w") as f:
            json.dump(result.to_dict(), f, indent=2, default=str)
        logger.info(f"Results saved to: {results_file}")

    # Save trades to logs/trades.json for Claude analysis
    logs_dir = Path(__file__).parent / "logs"
    logs_dir.mkdir(exist_ok=True)
    trades_file = logs_dir / "trades.json"
    trades_for_claude = []
    for trade in result.trades:
        trades_for_claude.append({
            "trade_id": f"bt_{timestamp}_{len(trades_for_claude)}",
            "timestamp_utc": trade.entry_date.isoformat() if trade.entry_date else None,
            "side": trade.side,
            "fill_price": trade.entry_price,
            "exit_time": trade.exit_date.isoformat() if trade.exit_date else None,
            "exit_price": trade.exit_price,
            "realized_pnl_usd": trade.pnl,
            "realized_pnl_percent": trade.pnl_pct,
        })
    with open(trades_file, "w") as f:
        json.dump(trades_for_claude, f, indent=2, default=str)
    logger.info(f"Trades saved for Claude: {trades_file} ({len(trades_for_claude)} trades)")

    # Generate PDF report
    if generate_pdf:
        if PDF_AVAILABLE:
            pdf_dir = REPORTS_DIR / "pdf"
            pdf_dir.mkdir(exist_ok=True)
            pdf_gen = PDFReportGenerator(output_dir=pdf_dir)
            pdf_path = pdf_gen.generate(result, f"backtest_report_{timestamp}.pdf")
            logger.info(f"PDF report saved to: {pdf_path}")
        else:
            logger.warning("PDF generator not available")

    # Save to Firestore
    if save_to_db:
        if FIRESTORE_AVAILABLE:
            try:
                # Use existing firestore_client if available, else create new
                firestore = firestore_client if firestore_client else FirestoreClient()

                # Create strategy if none exists
                if not strategy_id:
                    settings = get_settings()
                    strategy_id = firestore.create_strategy(
                        config=settings.strategy,
                        created_by="backtest_runner"
                    )
                    firestore.activate_strategy(strategy_id)
                    logger.info(f"Created initial strategy: {strategy_id}")

                # Get market condition for this period
                market_condition = None
                try:
                    from strategy.regime import RegimeClassifier
                    classifier = RegimeClassifier()
                    condition = classifier.classify("TQQQ", start_date, end_date)
                    if condition:
                        market_condition = condition.to_dict()
                        market_condition["embedding_text"] = condition.to_embedding_text()
                except Exception as e:
                    logger.warning(f"Failed to classify market condition: {e}")

                # Save session (backtest result)
                session_id = firestore.create_session(
                    strategy_id=strategy_id,
                    date=datetime.utcnow(),
                    total_pnl=result.metrics.total_return,
                    win_rate=result.metrics.win_rate,
                    max_drawdown=abs(result.metrics.max_drawdown),
                    sharpe_ratio=result.metrics.sharpe_ratio,
                    trade_count=result.metrics.total_trades,
                    period_start=start_date,
                    period_end=end_date,
                    market_condition=market_condition,
                )
                logger.info(f"Session saved to Firestore: {session_id}")

                # Log each trade
                for trade in result.trades:
                    firestore.log_trade(
                        strategy_id=strategy_id,
                        symbol=result.parameters.get("symbol", "TQQQ"),
                        side=trade.side,
                        entry_time=trade.entry_date,
                        entry_price=trade.entry_price,
                        quantity=trade.quantity,
                        exit_time=trade.exit_date,
                        exit_price=trade.exit_price,
                        pnl=trade.pnl,
                        pnl_percent=trade.pnl_pct,
                    )
                logger.info(f"Logged {len(result.trades)} trades to Firestore")

            except Exception as e:
                logger.error(f"Failed to save to Firestore: {e}")
        else:
            logger.warning("Firestore not available")

    # Send Discord notification
    if send_discord:
        notifier = DiscordNotifier()
        if notifier.enabled:
            notifier.send_backtest_report(result)
            logger.info("Discord notification sent")
        else:
            logger.warning("Discord webhook not configured")

    # Generate plots
    if plot:
        try:
            generate_plots(result)
        except ImportError:
            logger.warning("matplotlib not available for plotting")

    return result.to_dict()


def run_optimization() -> dict:
    """
    Run parameter optimization.

    Returns:
        Optimization results
    """
    logger.info("=" * 60)
    logger.info("TQQQ RSI(2) Strategy Optimization")
    logger.info("=" * 60)

    optimizer = StrategyOptimizer()

    result = optimizer.grid_search(
        rsi_periods=[2, 3],
        rsi_oversold_levels=[5, 10, 15, 20],
        rsi_overbought_levels=[65, 70, 75, 80],
        stop_loss_pcts=[0.03, 0.05, 0.07],
    )

    print("\n" + result.format_summary())

    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = REPORTS_DIR / f"optimization_{timestamp}.json"

    df = result.to_dataframe()
    df.to_csv(REPORTS_DIR / f"optimization_{timestamp}.csv", index=False)

    with open(results_file, "w") as f:
        json.dump({
            "best_params": result.best_params,
            "best_sharpe": result.best_sharpe,
            "best_result": result.best_result.to_dict(),
        }, f, indent=2, default=str)

    logger.info(f"Results saved to: {results_file}")

    return result.best_params


def generate_plots(result):
    """Generate visualization plots."""
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates

    fig, axes = plt.subplots(3, 1, figsize=(12, 10))

    # Equity curve
    ax1 = axes[0]
    ax1.plot(result.equity_curve.index, result.equity_curve.values, "b-", linewidth=1)
    ax1.set_title("Equity Curve")
    ax1.set_ylabel("Portfolio Value ($)")
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # Drawdown
    ax2 = axes[1]
    ax2.fill_between(
        result.drawdown_curve.index,
        result.drawdown_curve.values,
        0,
        color="red",
        alpha=0.3,
    )
    ax2.plot(result.drawdown_curve.index, result.drawdown_curve.values, "r-", linewidth=1)
    ax2.set_title("Drawdown")
    ax2.set_ylabel("Drawdown (%)")
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m"))

    # Trade P&L distribution
    ax3 = axes[2]
    pnls = [t.pnl for t in result.trades if t.pnl != 0]
    if pnls:
        colors = ["green" if p > 0 else "red" for p in pnls]
        ax3.bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
        ax3.axhline(y=0, color="black", linestyle="-", linewidth=0.5)
        ax3.set_title("Trade P&L Distribution")
        ax3.set_xlabel("Trade #")
        ax3.set_ylabel("P&L ($)")
        ax3.grid(True, alpha=0.3)

    plt.tight_layout()

    # Save plot
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    plot_file = REPORTS_DIR / f"backtest_plot_{timestamp}.png"
    plt.savefig(plot_file, dpi=150, bbox_inches="tight")
    logger.info(f"Plot saved to: {plot_file}")

    plt.show()


def get_period_dates(period: str, weeks_ago: int = 0) -> tuple[str, str]:
    """
    Get start/end dates for a named period.

    Args:
        period: Period name (this-week, last-week, this-month, last-month,
                last-30d, last-90d, ytd, random)
        weeks_ago: Number of weeks to go back (for weeks-ago option)

    Returns:
        Tuple of (start_date, end_date) as strings
    """
    import random
    from datetime import datetime, timedelta

    today = datetime.now()

    if period == "this-week":
        # 이번 주 (월~오늘)
        start = today - timedelta(days=today.weekday())
        end = today
    elif period == "last-week":
        # 지난 주 (월~일)
        start = today - timedelta(days=today.weekday() + 7)
        end = start + timedelta(days=6)
    elif period == "this-month":
        # 이번 달
        start = today.replace(day=1)
        end = today
    elif period == "last-month":
        # 지난 달
        first_of_month = today.replace(day=1)
        end = first_of_month - timedelta(days=1)
        start = end.replace(day=1)
    elif period == "last-30d":
        start = today - timedelta(days=30)
        end = today
    elif period == "last-90d":
        start = today - timedelta(days=90)
        end = today
    elif period == "ytd":
        # Year to date
        start = today.replace(month=1, day=1)
        end = today
    elif period == "random":
        # 최근 1년 내 랜덤 7일 구간
        max_days_back = 365
        random_offset = random.randint(7, max_days_back)
        end = today - timedelta(days=random_offset)
        start = end - timedelta(days=7)
    elif period == "weeks-ago":
        # N주 전의 7일 기간
        end = today - timedelta(weeks=weeks_ago)
        start = end - timedelta(days=7)
    else:
        # Default: last 7 days
        start = today - timedelta(days=7)
        end = today

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="TQQQ RSI(2) Mean Reversion Backtest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Period shortcuts (--period):
  this-week    이번 주 (월요일~오늘)
  last-week    지난 주 (월~일)
  this-month   이번 달
  last-month   지난 달
  last-30d     최근 30일
  last-90d     최근 90일
  ytd          올해 (1/1~오늘)
  random       최근 1년 내 랜덤 7일

Examples:
  python backtest_runner.py --period last-week
  python backtest_runner.py --period random
  python backtest_runner.py --weeks-ago 3
  python backtest_runner.py --start 2024-01-01 --end 2024-03-31
"""
    )

    # Default: last 7 days
    from datetime import datetime, timedelta
    default_end = datetime.now().strftime("%Y-%m-%d")
    default_start = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    parser.add_argument(
        "--start",
        type=str,
        default=None,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=str,
        default=None,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--period",
        type=str,
        choices=["this-week", "last-week", "this-month", "last-month",
                 "last-30d", "last-90d", "ytd", "random"],
        help="Use predefined period instead of start/end dates",
    )
    parser.add_argument(
        "--weeks-ago",
        type=int,
        default=None,
        help="Test 7-day period from N weeks ago (e.g., --weeks-ago 2)",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=10000.0,
        help="Initial capital",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Run parameter optimization",
    )
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Generate plots",
    )
    parser.add_argument(
        "--discord",
        action="store_true",
        help="Send results to Discord",
    )
    parser.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save results to file",
    )
    parser.add_argument(
        "--pdf",
        action="store_true",
        help="Generate PDF report",
    )
    parser.add_argument(
        "--db",
        action="store_true",
        help="Save results to Firestore database",
    )

    args = parser.parse_args()

    # Determine dates
    if args.period:
        start_date, end_date = get_period_dates(args.period)
        logger.info(f"Using period '{args.period}': {start_date} ~ {end_date}")
    elif args.weeks_ago is not None:
        start_date, end_date = get_period_dates("weeks-ago", args.weeks_ago)
        logger.info(f"Using {args.weeks_ago} weeks ago: {start_date} ~ {end_date}")
    elif args.start and args.end:
        start_date, end_date = args.start, args.end
    else:
        start_date, end_date = default_start, default_end

    try:
        if args.optimize:
            run_optimization()
        else:
            run_backtest(
                start_date=start_date,
                end_date=end_date,
                initial_capital=args.capital,
                save_results=not args.no_save,
                send_discord=args.discord,
                plot=args.plot,
                generate_pdf=args.pdf,
                save_to_db=args.db,
            )
    except KeyboardInterrupt:
        logger.info("Backtest interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.exception(f"Backtest failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
