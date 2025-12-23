"""
Backtest engine for RSI(2) Mean Reversion strategy.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

from config.settings import get_settings
from data.fetcher import DataFetcher
from data.storage import DataStorage
from execution.portfolio import Portfolio
from strategy.indicators import add_all_indicators
from strategy.signals import SignalGenerator
from strategy.risk_manager import RiskManager
from backtest.metrics import MetricsCalculator, PerformanceMetrics
from backtest.resource_monitor import ResourceMonitor, ResourceUsage

logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    """Record of a single backtest trade."""
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    quantity: float = 0.0
    side: str = "BUY"  # BUY (long) or SHORT
    pnl: float = 0.0
    pnl_pct: float = 0.0
    holding_days: int = 0
    entry_reason: str = ""
    exit_reason: str = ""

    @property
    def is_short(self) -> bool:
        """Check if this is a short trade."""
        return self.side == "SHORT"

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
            "entry_price": self.entry_price,
            "exit_date": self.exit_date.isoformat() if self.exit_date else None,
            "exit_price": self.exit_price,
            "quantity": self.quantity,
            "side": self.side,
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "holding_days": self.holding_days,
            "entry_reason": self.entry_reason,
            "exit_reason": self.exit_reason,
        }


@dataclass
class BacktestResult:
    """Complete backtest results."""
    metrics: PerformanceMetrics
    resource_usage: ResourceUsage
    equity_curve: pd.Series
    drawdown_curve: pd.Series
    trades: list[BacktestTrade]
    parameters: dict
    start_date: str
    end_date: str
    initial_capital: float
    final_equity: float

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "metrics": self.metrics.to_dict(),
            "resource_usage": self.resource_usage.to_dict(),
            "parameters": self.parameters,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "initial_capital": self.initial_capital,
            "final_equity": round(self.final_equity, 2),
            "total_trades": len(self.trades),
            "trades": [t.to_dict() for t in self.trades],
        }

    def format_report(self) -> str:
        """Format as text report."""
        report = []
        report.append("=" * 60)
        report.append("BACKTEST REPORT - RSI(2) TQQQ Mean Reversion")
        report.append("=" * 60)
        report.append("")
        report.append(f"Period: {self.start_date} to {self.end_date}")
        report.append(f"Initial Capital: ${self.initial_capital:,.2f}")
        report.append(f"Final Equity: ${self.final_equity:,.2f}")
        report.append("")
        report.append("-" * 60)
        report.append("PERFORMANCE METRICS")
        report.append("-" * 60)
        report.append(f"Total Return: ${self.metrics.total_return:,.2f} ({self.metrics.total_return_pct:+.2f}%)")
        report.append(f"CAGR: {self.metrics.cagr:+.2f}%")
        report.append(f"Sharpe Ratio: {self.metrics.sharpe_ratio:.3f}")
        report.append(f"Sortino Ratio: {self.metrics.sortino_ratio:.3f}")
        report.append(f"Max Drawdown: {self.metrics.max_drawdown:.2f}%")
        report.append(f"Calmar Ratio: {self.metrics.calmar_ratio:.3f}")
        report.append(f"Volatility: {self.metrics.volatility:.2f}%")
        report.append("")
        report.append("-" * 60)
        report.append("TRADE STATISTICS")
        report.append("-" * 60)
        report.append(f"Total Trades: {self.metrics.total_trades}")
        report.append(f"Winning Trades: {self.metrics.winning_trades}")
        report.append(f"Losing Trades: {self.metrics.losing_trades}")
        report.append(f"Win Rate: {self.metrics.win_rate:.1f}%")
        report.append(f"Profit Factor: {self.metrics.profit_factor:.3f}")
        report.append(f"Avg Win: ${self.metrics.avg_win:.2f}")
        report.append(f"Avg Loss: ${self.metrics.avg_loss:.2f}")
        report.append(f"Best Trade: ${self.metrics.best_trade:.2f}")
        report.append(f"Worst Trade: ${self.metrics.worst_trade:.2f}")
        report.append(f"Avg Trade Duration: {self.metrics.avg_trade_duration_days:.1f} days")
        report.append(f"Market Exposure: {self.metrics.exposure_pct:.1f}%")
        report.append("")
        report.append("-" * 60)
        report.append("RESOURCE USAGE")
        report.append("-" * 60)
        report.append(f"Execution Time: {self.resource_usage.execution_time_seconds:.2f}s")
        report.append(f"Peak Memory: {self.resource_usage.peak_memory_mb:.1f}MB")
        report.append(f"API Calls: {self.resource_usage.api_calls}")
        report.append(f"Data Points: {self.resource_usage.data_points_processed:,}")
        report.append(f"Est. Cost: ${self.resource_usage.total_estimated_cost_usd:.4f}")
        report.append("")
        report.append("-" * 60)
        report.append("PARAMETERS")
        report.append("-" * 60)
        for key, value in self.parameters.items():
            report.append(f"{key}: {value}")
        report.append("=" * 60)

        return "\n".join(report)


class BacktestEngine:
    """Engine for running backtests."""

    def __init__(
        self,
        initial_capital: Optional[float] = None,
        commission: float = 0.0,
        slippage_pct: float = 0.001,
    ):
        """
        Initialize backtest engine.

        Args:
            initial_capital: Starting capital
            commission: Commission per trade
            slippage_pct: Slippage percentage
        """
        settings = get_settings()
        self.initial_capital = initial_capital or settings.backtest.initial_capital
        self.commission = commission
        self.slippage_pct = slippage_pct

        self.data_fetcher = DataFetcher()
        self.data_storage = DataStorage()
        self.signal_generator = SignalGenerator()
        self.risk_manager = RiskManager()
        self.metrics_calculator = MetricsCalculator()
        self.resource_monitor = ResourceMonitor()

    def run(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> BacktestResult:
        """
        Run backtest.

        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            symbol: Symbol to trade

        Returns:
            BacktestResult with all metrics and data
        """
        settings = get_settings()
        start_date = start_date or settings.backtest.start_date
        end_date = end_date or settings.backtest.end_date
        symbol = symbol or settings.strategy.symbol

        logger.info(f"Starting backtest: {symbol} from {start_date} to {end_date}")

        # Start resource monitoring
        self.resource_monitor.start()

        # Fetch data for primary symbol (TQQQ)
        df = self._get_data(symbol, start_date, end_date)
        self.resource_monitor.record_data_points(len(df))

        # Fetch data for inverse ETF (SQQQ) if enabled
        hedge_df = None
        if settings.strategy.short_enabled and settings.strategy.use_inverse_etf:
            inverse_symbol = settings.strategy.inverse_symbol
            logger.info(f"Fetching hedge symbol data: {inverse_symbol}")
            try:
                hedge_df = self._get_data(inverse_symbol, start_date, end_date)
                self.resource_monitor.record_data_points(len(hedge_df))
                logger.info(f"Fetched {len(hedge_df)} bars for {inverse_symbol}")
            except Exception as e:
                logger.warning(f"Could not fetch hedge symbol data: {e}")
                hedge_df = None

        # Add indicators
        df = add_all_indicators(
            df,
            rsi_period=settings.strategy.rsi_period,
            sma_period=settings.strategy.sma_period,
        )

        # Initialize portfolio
        portfolio = Portfolio(initial_capital=self.initial_capital)

        # Run simulation
        equity_curve, trades = self._simulate(df, portfolio, symbol, hedge_df=hedge_df)

        # Calculate metrics
        metrics = self.metrics_calculator.calculate(
            equity_curve=equity_curve,
            trades=[t.to_dict() for t in trades],
            initial_capital=self.initial_capital,
        )

        # Get drawdown curve
        drawdown_curve = self.metrics_calculator.get_drawdown_series(equity_curve)

        # Stop resource monitoring
        resource_usage = self.resource_monitor.stop()
        resource_usage.trades_executed = len(trades)
        resource_usage.api_calls = self.data_fetcher.api_calls

        # Create result
        result = BacktestResult(
            metrics=metrics,
            resource_usage=resource_usage,
            equity_curve=equity_curve,
            drawdown_curve=drawdown_curve,
            trades=trades,
            parameters=self._get_parameters(),
            start_date=start_date,
            end_date=end_date,
            initial_capital=self.initial_capital,
            final_equity=portfolio.equity,
        )

        logger.info(f"Backtest complete: {metrics.total_trades} trades, "
                   f"{metrics.total_return_pct:+.2f}% return")

        return result

    def _get_data(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        """Fetch or load cached data with warmup period for indicators."""
        settings = get_settings()

        # Calculate warmup start date (need extra days for SMA calculation)
        warmup_days = settings.strategy.sma_period + 10  # SMA period + buffer
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        warmup_start = (start_dt - timedelta(days=warmup_days * 1.5)).strftime("%Y-%m-%d")
        # 1.5x multiplier to account for weekends/holidays

        logger.info(f"Fetching data from {warmup_start} to {end_date} (warmup for SMA-{settings.strategy.sma_period})")

        # Check cache first
        cached = self.data_storage.load_bars(symbol, "daily", warmup_start, end_date)
        if cached is not None:
            return cached

        # Fetch from API with warmup period
        df = self.data_fetcher.get_daily_bars(symbol, warmup_start, end_date)
        self.resource_monitor.record_api_call()

        # Cache for future use
        if len(df) > 0:
            self.data_storage.save_bars(df, symbol, "daily", warmup_start, end_date)

        return df

    def _simulate(
        self,
        df: pd.DataFrame,
        portfolio: Portfolio,
        symbol: str,
        hedge_df: Optional[pd.DataFrame] = None,
    ) -> tuple[pd.Series, list[BacktestTrade]]:
        """
        Run trading simulation with long, short, and hedge (SQQQ) support.

        Args:
            df: DataFrame with OHLCV and indicators for primary symbol (TQQQ)
            portfolio: Portfolio to trade
            symbol: Primary symbol (TQQQ)
            hedge_df: DataFrame for hedge symbol (SQQQ) if using inverse ETF

        Returns:
            Tuple of (equity_curve, trades)
        """
        from config.constants import SignalType

        settings = get_settings()
        trades: list[BacktestTrade] = []
        equity_values = []
        dates = []

        current_trade: Optional[BacktestTrade] = None
        entry_price: Optional[float] = None  # TQQQ entry price
        hedge_entry_price: Optional[float] = None  # SQQQ entry price
        position_side: Optional[str] = None  # "long", "short", or "hedge"

        # Skip first SMA_PERIOD days for indicator warmup
        warmup = settings.strategy.sma_period
        if len(df) <= warmup:
            logger.warning("Insufficient data for backtest")
            return pd.Series(dtype=float), []

        for i in range(warmup, len(df)):
            current_date = df.index[i]
            current_data = df.iloc[:i+1]
            current_bar = df.iloc[i]

            # Get hedge symbol data if available
            hedge_bar = None
            if hedge_df is not None and current_date in hedge_df.index:
                hedge_bar = hedge_df.loc[current_date]

            # Check for signals
            has_position = portfolio.has_position

            if has_position and entry_price is not None:
                # Check for exit based on position type
                current_hedge_price = hedge_bar["close"] if hedge_bar is not None else None
                signal = self.signal_generator.generate_signals(
                    current_data,
                    has_position=True,
                    entry_price=entry_price,
                    stop_loss_pct=settings.strategy.stop_loss_pct,
                    position_side=position_side,
                    short_stop_loss_pct=settings.strategy.short_stop_loss_pct,
                    hedge_entry_price=hedge_entry_price,
                    current_hedge_price=current_hedge_price,
                )

                exit_signal_types = (SignalType.SELL, SignalType.COVER, SignalType.HEDGE_SELL)
                if signal and signal.signal_type in exit_signal_types:
                    # Determine exit price based on position type
                    if position_side == "hedge" and hedge_bar is not None:
                        # Exit SQQQ position
                        exit_price = hedge_bar["close"] * (1 - self.slippage_pct)
                        position = portfolio.get_position(settings.strategy.inverse_symbol)
                        trade_symbol = settings.strategy.inverse_symbol
                    elif position_side == "short":
                        exit_price = current_bar["close"] * (1 + self.slippage_pct)
                        position = portfolio.get_position(symbol)
                        trade_symbol = symbol
                    else:
                        exit_price = current_bar["close"] * (1 - self.slippage_pct)
                        position = portfolio.get_position(symbol)
                        trade_symbol = symbol

                    if position:
                        pnl = portfolio.close_position(
                            symbol=trade_symbol,
                            price=exit_price,
                            timestamp=current_date if isinstance(current_date, datetime) else current_date.to_pydatetime(),
                            commission=self.commission,
                        )

                        # For shorts, recalculate PnL
                        if position_side == "short":
                            pnl = (entry_price - exit_price) * current_trade.quantity - self.commission

                        # Complete trade record
                        if current_trade:
                            current_trade.exit_date = current_date if isinstance(current_date, datetime) else current_date.to_pydatetime()
                            current_trade.exit_price = exit_price
                            current_trade.pnl = pnl
                            if position_side == "hedge" and hedge_entry_price:
                                current_trade.pnl_pct = (pnl / (hedge_entry_price * current_trade.quantity)) * 100
                            else:
                                current_trade.pnl_pct = (pnl / (entry_price * current_trade.quantity)) * 100
                            current_trade.holding_days = (current_trade.exit_date - current_trade.entry_date).days
                            current_trade.exit_reason = signal.reason
                            trades.append(current_trade)

                        current_trade = None
                        entry_price = None
                        hedge_entry_price = None
                        position_side = None
                        self.resource_monitor.record_trade()

            else:
                # Check for entry (long, short, or hedge)
                signal = self.signal_generator.generate_signals(
                    current_data,
                    has_position=False,
                )

                if signal and signal.signal_type == SignalType.BUY:
                    # Long entry (TQQQ)
                    pos_size = self.risk_manager.calculate_position_size(
                        account_value=portfolio.equity,
                        current_price=current_bar["close"],
                        use_fractional=True,
                    )

                    if pos_size.shares > 0:
                        buy_price = current_bar["close"] * (1 + self.slippage_pct)

                        try:
                            portfolio.open_position(
                                symbol=symbol,
                                quantity=pos_size.shares,
                                price=buy_price,
                                timestamp=current_date if isinstance(current_date, datetime) else current_date.to_pydatetime(),
                                commission=self.commission,
                            )

                            entry_price = buy_price
                            position_side = "long"

                            current_trade = BacktestTrade(
                                entry_date=current_date if isinstance(current_date, datetime) else current_date.to_pydatetime(),
                                entry_price=buy_price,
                                quantity=pos_size.shares,
                                side="BUY",
                                entry_reason=signal.reason,
                            )

                        except ValueError as e:
                            logger.warning(f"Could not open long position: {e}")

                elif signal and signal.signal_type == SignalType.HEDGE_BUY and hedge_bar is not None:
                    # Hedge entry: Buy SQQQ instead of shorting TQQQ
                    pos_size = self.risk_manager.calculate_position_size(
                        account_value=portfolio.equity,
                        current_price=hedge_bar["close"],
                        use_fractional=True,
                        position_size_pct=settings.strategy.short_position_size_pct,
                    )

                    if pos_size.shares > 0:
                        buy_price = hedge_bar["close"] * (1 + self.slippage_pct)

                        try:
                            portfolio.open_position(
                                symbol=settings.strategy.inverse_symbol,
                                quantity=pos_size.shares,
                                price=buy_price,
                                timestamp=current_date if isinstance(current_date, datetime) else current_date.to_pydatetime(),
                                commission=self.commission,
                            )

                            entry_price = current_bar["close"]  # TQQQ price for RSI tracking
                            hedge_entry_price = buy_price  # SQQQ price for stop loss
                            position_side = "hedge"

                            current_trade = BacktestTrade(
                                entry_date=current_date if isinstance(current_date, datetime) else current_date.to_pydatetime(),
                                entry_price=buy_price,
                                quantity=pos_size.shares,
                                side="HEDGE",
                                entry_reason=signal.reason,
                            )

                            logger.info(f"HEDGE position opened: {pos_size.shares:.2f} SQQQ @ ${buy_price:.2f}")

                        except ValueError as e:
                            logger.warning(f"Could not open hedge position: {e}")

                elif signal and signal.signal_type == SignalType.SHORT:
                    # Direct short entry (TQQQ)
                    pos_size = self.risk_manager.calculate_position_size(
                        account_value=portfolio.equity,
                        current_price=current_bar["close"],
                        use_fractional=True,
                        position_size_pct=settings.strategy.short_position_size_pct,
                    )

                    if pos_size.shares > 0:
                        short_price = current_bar["close"] * (1 - self.slippage_pct)

                        try:
                            portfolio.open_position(
                                symbol=symbol,
                                quantity=pos_size.shares,
                                price=short_price,
                                timestamp=current_date if isinstance(current_date, datetime) else current_date.to_pydatetime(),
                                commission=self.commission,
                            )

                            entry_price = short_price
                            position_side = "short"

                            current_trade = BacktestTrade(
                                entry_date=current_date if isinstance(current_date, datetime) else current_date.to_pydatetime(),
                                entry_price=short_price,
                                quantity=pos_size.shares,
                                side="SHORT",
                                entry_reason=signal.reason,
                            )

                        except ValueError as e:
                            logger.warning(f"Could not open short position: {e}")

            # Update portfolio prices
            if portfolio.has_position:
                if position_side == "long":
                    portfolio.update_prices({symbol: current_bar["close"]})
                elif position_side == "hedge" and hedge_bar is not None:
                    portfolio.update_prices({settings.strategy.inverse_symbol: hedge_bar["close"]})

            # Record equity
            equity_values.append(portfolio.equity)
            dates.append(current_date)

        # Close any remaining position at end
        if portfolio.has_position and current_trade:
            if position_side == "hedge" and hedge_df is not None:
                final_price = hedge_df.iloc[-1]["close"]
                trade_symbol = settings.strategy.inverse_symbol
                pnl = portfolio.close_position(symbol=trade_symbol, price=final_price)
            elif position_side == "short":
                final_price = df.iloc[-1]["close"]
                trade_symbol = symbol
                pnl = (entry_price - final_price) * current_trade.quantity - self.commission
            else:
                final_price = df.iloc[-1]["close"]
                trade_symbol = symbol
                pnl = portfolio.close_position(symbol=trade_symbol, price=final_price)

            current_trade.exit_date = df.index[-1] if isinstance(df.index[-1], datetime) else df.index[-1].to_pydatetime()
            current_trade.exit_price = final_price
            current_trade.pnl = pnl
            if position_side == "hedge" and hedge_entry_price:
                current_trade.pnl_pct = (pnl / (hedge_entry_price * current_trade.quantity)) * 100
            elif entry_price:
                current_trade.pnl_pct = (pnl / (entry_price * current_trade.quantity)) * 100
            current_trade.holding_days = (current_trade.exit_date - current_trade.entry_date).days
            current_trade.exit_reason = "End of backtest period"
            trades.append(current_trade)

        equity_curve = pd.Series(equity_values, index=dates)
        return equity_curve, trades

    def _get_parameters(self) -> dict:
        """Get strategy parameters."""
        settings = get_settings()
        return {
            "symbol": settings.strategy.symbol,
            "rsi_period": settings.strategy.rsi_period,
            "rsi_oversold": settings.strategy.rsi_oversold,
            "rsi_overbought": settings.strategy.rsi_overbought,
            "sma_period": settings.strategy.sma_period,
            "stop_loss_pct": settings.strategy.stop_loss_pct,
            "position_size_pct": settings.strategy.position_size_pct,
            # Hedge/Short parameters
            "short_enabled": settings.strategy.short_enabled,
            "use_inverse_etf": settings.strategy.use_inverse_etf,
            "inverse_symbol": settings.strategy.inverse_symbol,
            "rsi_overbought_short": settings.strategy.rsi_overbought_short,
            "rsi_oversold_short": settings.strategy.rsi_oversold_short,
            "short_stop_loss_pct": settings.strategy.short_stop_loss_pct,
            "short_position_size_pct": settings.strategy.short_position_size_pct,
            # Backtest settings
            "initial_capital": self.initial_capital,
            "commission": self.commission,
            "slippage_pct": self.slippage_pct,
        }
