"""
Parameter optimization for strategy.
"""
import logging
from dataclasses import dataclass
from itertools import product
from typing import Optional

import pandas as pd

from backtest.engine import BacktestEngine, BacktestResult
from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class OptimizationResult:
    """Result of parameter optimization."""
    best_params: dict
    best_sharpe: float
    best_result: BacktestResult
    all_results: list[dict]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert all results to DataFrame."""
        return pd.DataFrame(self.all_results)

    def format_summary(self) -> str:
        """Format optimization summary."""
        lines = []
        lines.append("=" * 60)
        lines.append("OPTIMIZATION RESULTS")
        lines.append("=" * 60)
        lines.append("")
        lines.append("Best Parameters:")
        for key, value in self.best_params.items():
            lines.append(f"  {key}: {value}")
        lines.append("")
        lines.append(f"Best Sharpe Ratio: {self.best_sharpe:.3f}")
        lines.append(f"Total Return: {self.best_result.metrics.total_return_pct:+.2f}%")
        lines.append(f"Max Drawdown: {self.best_result.metrics.max_drawdown:.2f}%")
        lines.append(f"Win Rate: {self.best_result.metrics.win_rate:.1f}%")
        lines.append("")
        lines.append(f"Total combinations tested: {len(self.all_results)}")
        lines.append("=" * 60)
        return "\n".join(lines)


class StrategyOptimizer:
    """Optimize strategy parameters."""

    def __init__(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_capital: float = 10000.0,
    ):
        """
        Initialize optimizer.

        Args:
            start_date: Backtest start date
            end_date: Backtest end date
            initial_capital: Starting capital
        """
        settings = get_settings()
        self.start_date = start_date or settings.backtest.start_date
        self.end_date = end_date or settings.backtest.end_date
        self.initial_capital = initial_capital

    def grid_search(
        self,
        rsi_periods: list[int] = [2, 3, 4],
        rsi_oversold_levels: list[float] = [5, 10, 15],
        rsi_overbought_levels: list[float] = [60, 70, 80],
        stop_loss_pcts: list[float] = [0.03, 0.05, 0.07],
        optimize_for: str = "sharpe",
    ) -> OptimizationResult:
        """
        Run grid search optimization.

        Args:
            rsi_periods: RSI periods to test
            rsi_oversold_levels: Oversold thresholds to test
            rsi_overbought_levels: Overbought thresholds to test
            stop_loss_pcts: Stop loss percentages to test
            optimize_for: Metric to optimize (sharpe, return, calmar)

        Returns:
            OptimizationResult with best parameters
        """
        settings = get_settings()
        all_results = []
        best_result = None
        best_score = float("-inf")
        best_params = {}

        combinations = list(product(
            rsi_periods,
            rsi_oversold_levels,
            rsi_overbought_levels,
            stop_loss_pcts,
        ))

        logger.info(f"Starting grid search with {len(combinations)} combinations")

        for i, (rsi_period, rsi_oversold, rsi_overbought, stop_loss) in enumerate(combinations):
            # Skip invalid combinations
            if rsi_oversold >= rsi_overbought:
                continue

            # Update settings
            settings.strategy.rsi_period = rsi_period
            settings.strategy.rsi_oversold = rsi_oversold
            settings.strategy.rsi_overbought = rsi_overbought
            settings.strategy.stop_loss_pct = stop_loss

            # Run backtest
            try:
                engine = BacktestEngine(initial_capital=self.initial_capital)
                result = engine.run(
                    start_date=self.start_date,
                    end_date=self.end_date,
                )

                # Get optimization score
                if optimize_for == "sharpe":
                    score = result.metrics.sharpe_ratio
                elif optimize_for == "return":
                    score = result.metrics.total_return_pct
                elif optimize_for == "calmar":
                    score = result.metrics.calmar_ratio
                else:
                    score = result.metrics.sharpe_ratio

                params = {
                    "rsi_period": rsi_period,
                    "rsi_oversold": rsi_oversold,
                    "rsi_overbought": rsi_overbought,
                    "stop_loss_pct": stop_loss,
                }

                all_results.append({
                    **params,
                    "sharpe": result.metrics.sharpe_ratio,
                    "return_pct": result.metrics.total_return_pct,
                    "max_dd": result.metrics.max_drawdown,
                    "win_rate": result.metrics.win_rate,
                    "trades": result.metrics.total_trades,
                    "profit_factor": result.metrics.profit_factor,
                })

                if score > best_score:
                    best_score = score
                    best_result = result
                    best_params = params

                logger.debug(
                    f"[{i+1}/{len(combinations)}] "
                    f"RSI({rsi_period}, {rsi_oversold}/{rsi_overbought}), "
                    f"SL={stop_loss*100}% -> Sharpe: {result.metrics.sharpe_ratio:.3f}"
                )

            except Exception as e:
                logger.warning(f"Backtest failed for params: {e}")

        if best_result is None:
            raise ValueError("No valid backtest results")

        logger.info(f"Best parameters found: {best_params} (Sharpe: {best_score:.3f})")

        return OptimizationResult(
            best_params=best_params,
            best_sharpe=best_score,
            best_result=best_result,
            all_results=all_results,
        )

    def walk_forward(
        self,
        train_months: int = 6,
        test_months: int = 1,
        step_months: int = 1,
    ) -> dict:
        """
        Walk-forward optimization (simplified version).

        Args:
            train_months: Training period in months
            test_months: Testing period in months
            step_months: Step size in months

        Returns:
            Walk-forward results summary
        """
        # This is a placeholder for walk-forward optimization
        # Full implementation would require more complex date handling
        logger.info("Walk-forward optimization not yet implemented")
        return {
            "status": "not_implemented",
            "message": "Use grid_search for now",
        }
