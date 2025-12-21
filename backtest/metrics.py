"""
Performance metrics calculation for backtests.
"""
import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Comprehensive performance metrics."""
    # Returns
    total_return: float = 0.0
    total_return_pct: float = 0.0
    cagr: float = 0.0
    annualized_return: float = 0.0

    # Risk metrics
    volatility: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration_days: int = 0
    calmar_ratio: float = 0.0

    # Trade statistics
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_trade_duration_days: float = 0.0

    # Additional metrics
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_trade: float = 0.0
    trading_days: int = 0
    exposure_pct: float = 0.0

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "total_return": round(self.total_return, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "cagr": round(self.cagr, 2),
            "annualized_return": round(self.annualized_return, 2),
            "volatility": round(self.volatility, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 3),
            "sortino_ratio": round(self.sortino_ratio, 3),
            "max_drawdown": round(self.max_drawdown, 2),
            "max_drawdown_duration_days": self.max_drawdown_duration_days,
            "calmar_ratio": round(self.calmar_ratio, 3),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": round(self.win_rate, 2),
            "avg_win": round(self.avg_win, 2),
            "avg_loss": round(self.avg_loss, 2),
            "profit_factor": round(self.profit_factor, 3),
            "expectancy": round(self.expectancy, 2),
            "avg_trade_duration_days": round(self.avg_trade_duration_days, 1),
            "best_trade": round(self.best_trade, 2),
            "worst_trade": round(self.worst_trade, 2),
            "avg_trade": round(self.avg_trade, 2),
            "trading_days": self.trading_days,
            "exposure_pct": round(self.exposure_pct, 2),
        }

    def format_summary(self) -> str:
        """Format as human-readable summary."""
        return (
            f"📈 **Performance Summary**\n"
            f"Total Return: {self.total_return_pct:+.2f}%\n"
            f"CAGR: {self.cagr:+.2f}%\n"
            f"Sharpe Ratio: {self.sharpe_ratio:.2f}\n"
            f"Max Drawdown: {self.max_drawdown:.2f}%\n\n"
            f"📊 **Trade Statistics**\n"
            f"Total Trades: {self.total_trades}\n"
            f"Win Rate: {self.win_rate:.1f}%\n"
            f"Profit Factor: {self.profit_factor:.2f}\n"
            f"Avg Trade: ${self.avg_trade:.2f}"
        )


class MetricsCalculator:
    """Calculate performance metrics from backtest results."""

    TRADING_DAYS_PER_YEAR = 252
    RISK_FREE_RATE = 0.05  # 5% annual risk-free rate

    def __init__(self, risk_free_rate: float = 0.05):
        """
        Initialize metrics calculator.

        Args:
            risk_free_rate: Annual risk-free rate for Sharpe calculation
        """
        self.risk_free_rate = risk_free_rate

    def calculate(
        self,
        equity_curve: pd.Series,
        trades: list[dict],
        initial_capital: float,
    ) -> PerformanceMetrics:
        """
        Calculate all performance metrics.

        Args:
            equity_curve: Daily equity values (indexed by date)
            trades: List of trade dictionaries
            initial_capital: Starting capital

        Returns:
            PerformanceMetrics object
        """
        metrics = PerformanceMetrics()

        if len(equity_curve) < 2:
            return metrics

        # Basic returns
        final_equity = equity_curve.iloc[-1]
        metrics.total_return = final_equity - initial_capital
        metrics.total_return_pct = (metrics.total_return / initial_capital) * 100

        # Calculate daily returns
        returns = equity_curve.pct_change().dropna()
        metrics.trading_days = len(returns)

        # CAGR
        years = metrics.trading_days / self.TRADING_DAYS_PER_YEAR
        if years > 0 and final_equity > 0 and initial_capital > 0:
            metrics.cagr = ((final_equity / initial_capital) ** (1 / years) - 1) * 100
            metrics.annualized_return = metrics.cagr

        # Volatility (annualized)
        if len(returns) > 1:
            daily_vol = returns.std()
            metrics.volatility = daily_vol * np.sqrt(self.TRADING_DAYS_PER_YEAR) * 100

        # Sharpe Ratio
        if metrics.volatility > 0:
            excess_return = metrics.cagr - (self.risk_free_rate * 100)
            metrics.sharpe_ratio = excess_return / metrics.volatility

        # Sortino Ratio (only downside volatility)
        negative_returns = returns[returns < 0]
        if len(negative_returns) > 0:
            downside_vol = negative_returns.std() * np.sqrt(self.TRADING_DAYS_PER_YEAR) * 100
            if downside_vol > 0:
                excess_return = metrics.cagr - (self.risk_free_rate * 100)
                metrics.sortino_ratio = excess_return / downside_vol

        # Maximum Drawdown
        dd_info = self._calculate_drawdown(equity_curve)
        metrics.max_drawdown = dd_info["max_drawdown"]
        metrics.max_drawdown_duration_days = dd_info["max_duration"]

        # Calmar Ratio
        if abs(metrics.max_drawdown) > 0:
            metrics.calmar_ratio = metrics.cagr / abs(metrics.max_drawdown)

        # Trade statistics
        if trades:
            self._calculate_trade_stats(metrics, trades)

        # Exposure
        in_market_days = sum(1 for t in trades for _ in range(t.get("holding_days", 1) or 1))
        if metrics.trading_days > 0:
            metrics.exposure_pct = (in_market_days / metrics.trading_days) * 100

        return metrics

    def _calculate_drawdown(self, equity_curve: pd.Series) -> dict:
        """Calculate drawdown metrics."""
        rolling_max = equity_curve.expanding().max()
        drawdowns = (equity_curve - rolling_max) / rolling_max * 100

        max_dd = drawdowns.min()

        # Calculate max drawdown duration
        is_underwater = drawdowns < 0
        duration = 0
        max_duration = 0
        for underwater in is_underwater:
            if underwater:
                duration += 1
                max_duration = max(max_duration, duration)
            else:
                duration = 0

        return {
            "max_drawdown": max_dd,
            "max_duration": max_duration,
            "drawdowns": drawdowns,
        }

    def _calculate_trade_stats(
        self,
        metrics: PerformanceMetrics,
        trades: list[dict],
    ) -> None:
        """Calculate trade statistics."""
        pnls = [t.get("pnl", 0) for t in trades if "pnl" in t]

        if not pnls:
            return

        metrics.total_trades = len(pnls)
        metrics.winning_trades = sum(1 for p in pnls if p > 0)
        metrics.losing_trades = sum(1 for p in pnls if p <= 0)

        if metrics.total_trades > 0:
            metrics.win_rate = (metrics.winning_trades / metrics.total_trades) * 100

        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]

        if wins:
            metrics.avg_win = np.mean(wins)
            metrics.best_trade = max(wins)
        if losses:
            metrics.avg_loss = np.mean(losses)
            metrics.worst_trade = min(losses)

        # Profit Factor
        total_wins = sum(wins) if wins else 0
        total_losses = abs(sum(losses)) if losses else 0
        if total_losses > 0:
            metrics.profit_factor = total_wins / total_losses

        # Expectancy
        if metrics.total_trades > 0:
            metrics.avg_trade = np.mean(pnls)
            metrics.expectancy = (
                (metrics.win_rate / 100 * metrics.avg_win) +
                ((1 - metrics.win_rate / 100) * metrics.avg_loss)
            )

        # Average holding period
        holding_days = [t.get("holding_days", 1) for t in trades if t.get("holding_days")]
        if holding_days:
            metrics.avg_trade_duration_days = np.mean(holding_days)

    def get_drawdown_series(self, equity_curve: pd.Series) -> pd.Series:
        """Get drawdown series for plotting."""
        rolling_max = equity_curve.expanding().max()
        return (equity_curve - rolling_max) / rolling_max * 100
