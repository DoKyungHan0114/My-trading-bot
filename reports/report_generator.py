"""
Report generator for Claude analysis.
Generates structured reports with current strategy, trades, and market data.
"""
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from config.settings import StrategyConfig, get_settings
from data.fetcher import DataFetcher
from strategy.indicators import add_all_indicators

logger = logging.getLogger(__name__)


@dataclass
class MarketCondition:
    """Current market conditions."""

    symbol: str
    current_price: float
    daily_change_pct: float
    rsi: float
    above_sma200: bool
    sma200: float
    volatility_atr: float
    volume_ratio: float  # vs 20-day average
    trend: str  # "bullish", "bearish", "neutral"


@dataclass
class TradeSummary:
    """Summary of a single trade."""

    trade_id: str
    side: str
    entry_time: str
    entry_price: float
    exit_time: Optional[str]
    exit_price: Optional[float]
    pnl: Optional[float]
    pnl_percent: Optional[float]
    holding_hours: Optional[float]


@dataclass
class PerformanceSummary:
    """Performance metrics summary."""

    total_trades: int
    winning_trades: int
    losing_trades: int
    win_rate: float
    total_pnl: float
    avg_pnl_per_trade: float
    best_trade: float
    worst_trade: float
    avg_holding_hours: float
    max_drawdown: float


@dataclass
class AnalysisReport:
    """Complete analysis report for Claude."""

    report_id: str
    generated_at: str
    strategy: dict
    market_condition: dict
    todays_trades: list[dict]
    recent_performance: dict
    recommendations_context: str

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(asdict(self), indent=2, default=str)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return asdict(self)


class ReportGenerator:
    """Generate analysis reports for Claude."""

    def __init__(
        self,
        strategy_config: Optional[StrategyConfig] = None,
        data_fetcher: Optional[DataFetcher] = None,
    ):
        """
        Initialize report generator.

        Args:
            strategy_config: Current strategy configuration
            data_fetcher: Data fetcher instance
        """
        settings = get_settings()
        self.config = strategy_config or settings.strategy
        self.fetcher = data_fetcher or DataFetcher()
        self.reports_dir = Path("reports")
        self.reports_dir.mkdir(exist_ok=True)

    def get_market_condition(self) -> MarketCondition:
        """Get current market conditions."""
        symbol = self.config.symbol
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=250)).strftime("%Y-%m-%d")

        try:
            df = self.fetcher.get_daily_bars(symbol, start_date, end_date)
            if df.empty:
                return self._empty_market_condition()

            df = add_all_indicators(
                df,
                rsi_period=self.config.rsi_period,
                sma_period=self.config.sma_period,
            )

            latest = df.iloc[-1]
            prev = df.iloc[-2] if len(df) > 1 else latest

            # Dynamic SMA column name
            sma_col = f"sma_{self.config.sma_period}"

            # Calculate metrics
            current_price = float(latest["close"])
            daily_change = (current_price - float(prev["close"])) / float(
                prev["close"]
            )
            rsi = float(latest["rsi"]) if pd.notna(latest["rsi"]) else 50.0
            sma_value = float(latest[sma_col]) if sma_col in df.columns and pd.notna(latest[sma_col]) else 0.0
            atr = float(latest["atr"]) if pd.notna(latest["atr"]) else 0.0

            # Volume ratio (vs 20-day average)
            avg_volume = df["volume"].tail(20).mean()
            volume_ratio = float(latest["volume"]) / avg_volume if avg_volume > 0 else 1.0

            # Determine trend
            if current_price > sma_value and rsi > 50:
                trend = "bullish"
            elif current_price < sma_value and rsi < 50:
                trend = "bearish"
            else:
                trend = "neutral"

            return MarketCondition(
                symbol=symbol,
                current_price=current_price,
                daily_change_pct=daily_change * 100,
                rsi=rsi,
                above_sma200=current_price > sma_value,
                sma200=sma_value,
                volatility_atr=atr,
                volume_ratio=volume_ratio,
                trend=trend,
            )

        except Exception as e:
            logger.error(f"Failed to get market condition: {e}")
            return self._empty_market_condition()

    def _empty_market_condition(self) -> MarketCondition:
        """Return empty market condition."""
        return MarketCondition(
            symbol=self.config.symbol,
            current_price=0.0,
            daily_change_pct=0.0,
            rsi=50.0,
            above_sma200=False,
            sma200=0.0,
            volatility_atr=0.0,
            volume_ratio=1.0,
            trend="neutral",
        )

    def get_todays_trades(self, trades_file: str = "logs/trades.json") -> list[TradeSummary]:
        """
        Get recent trades from log file (past 7 days).

        Args:
            trades_file: Path to trades JSON file

        Returns:
            List of trade summaries
        """
        trades = []
        try:
            with open(trades_file, "r") as f:
                all_trades = json.load(f)

            # 10일 전 날짜 (백테스트 워밍업 고려)
            cutoff = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d")

            for trade in all_trades:
                trade_date = trade.get("timestamp_utc", "")[:10]
                if trade_date >= cutoff:  # 최근 7일 트레이드 모두 포함
                    # Calculate holding hours if exit exists
                    holding_hours = None
                    if trade.get("exit_time"):
                        entry = datetime.fromisoformat(trade["timestamp_utc"])
                        exit_time = datetime.fromisoformat(trade["exit_time"])
                        holding_hours = (exit_time - entry).total_seconds() / 3600

                    trades.append(
                        TradeSummary(
                            trade_id=trade.get("trade_id", "unknown"),
                            side=trade.get("side", "UNKNOWN"),
                            entry_time=trade.get("timestamp_utc", ""),
                            entry_price=trade.get("fill_price", 0.0),
                            exit_time=trade.get("exit_time"),
                            exit_price=trade.get("exit_price"),
                            pnl=trade.get("realized_pnl_usd"),
                            pnl_percent=trade.get("realized_pnl_percent"),
                            holding_hours=holding_hours,
                        )
                    )

        except FileNotFoundError:
            logger.warning(f"Trades file not found: {trades_file}")
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse trades file: {e}")

        return trades

    def calculate_recent_performance(
        self, trades_file: str = "logs/trades.json", days: int = 10  # 백테스트 워밍업 고려
    ) -> PerformanceSummary:
        """
        Calculate performance metrics for recent trades.

        Args:
            trades_file: Path to trades JSON file
            days: Number of days to look back

        Returns:
            Performance summary
        """
        try:
            with open(trades_file, "r") as f:
                all_trades = json.load(f)

            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            recent = [
                t for t in all_trades if t.get("timestamp_utc", "") >= cutoff
            ]

            if not recent:
                return self._empty_performance()

            # Calculate metrics
            pnls = [t.get("realized_pnl_usd", 0) or 0 for t in recent]
            winning = [p for p in pnls if p > 0]
            losing = [p for p in pnls if p < 0]

            total_pnl = sum(pnls)
            win_rate = len(winning) / len(recent) * 100 if recent else 0

            # Holding times
            holding_hours = []
            for t in recent:
                if t.get("exit_time") and t.get("timestamp_utc"):
                    entry = datetime.fromisoformat(t["timestamp_utc"])
                    exit_time = datetime.fromisoformat(t["exit_time"])
                    hours = (exit_time - entry).total_seconds() / 3600
                    holding_hours.append(hours)

            # Calculate max drawdown from equity curve
            equity = 10000  # Starting equity
            peak = equity
            max_dd = 0
            for pnl in pnls:
                equity += pnl
                peak = max(peak, equity)
                dd = (peak - equity) / peak * 100 if peak > 0 else 0
                max_dd = max(max_dd, dd)

            return PerformanceSummary(
                total_trades=len(recent),
                winning_trades=len(winning),
                losing_trades=len(losing),
                win_rate=win_rate,
                total_pnl=total_pnl,
                avg_pnl_per_trade=total_pnl / len(recent) if recent else 0,
                best_trade=max(pnls) if pnls else 0,
                worst_trade=min(pnls) if pnls else 0,
                avg_holding_hours=sum(holding_hours) / len(holding_hours) if holding_hours else 0,
                max_drawdown=max_dd,
            )

        except FileNotFoundError:
            logger.warning(f"Trades file not found: {trades_file}")
            return self._empty_performance()
        except Exception as e:
            logger.error(f"Failed to calculate performance: {e}")
            return self._empty_performance()

    def _empty_performance(self) -> PerformanceSummary:
        """Return empty performance summary."""
        return PerformanceSummary(
            total_trades=0,
            winning_trades=0,
            losing_trades=0,
            win_rate=0.0,
            total_pnl=0.0,
            avg_pnl_per_trade=0.0,
            best_trade=0.0,
            worst_trade=0.0,
            avg_holding_hours=0.0,
            max_drawdown=0.0,
        )

    def generate_recommendations_context(
        self,
        market: MarketCondition,
        performance: PerformanceSummary,
    ) -> str:
        """
        Generate context string for Claude recommendations.

        Args:
            market: Current market conditions
            performance: Recent performance summary

        Returns:
            Context string for Claude prompt
        """
        context_parts = []

        # Market analysis
        if market.rsi < 20:
            context_parts.append("RSI is extremely oversold - potential buying opportunity")
        elif market.rsi > 80:
            context_parts.append("RSI is extremely overbought - consider tightening exits")

        if not market.above_sma200:
            context_parts.append("Price below SMA200 - trend filter blocking entries")

        if market.volatility_atr > market.current_price * 0.05:
            context_parts.append("High volatility detected - consider adjusting position sizing")

        if market.volume_ratio > 2.0:
            context_parts.append("Unusual volume - potential trend continuation")

        # Performance analysis
        if performance.win_rate < 40:
            context_parts.append(
                f"Low win rate ({performance.win_rate:.1f}%) - "
                "consider adjusting entry criteria"
            )

        if performance.max_drawdown > 10:
            context_parts.append(
                f"High drawdown ({performance.max_drawdown:.1f}%) - "
                "review risk management"
            )

        if performance.avg_holding_hours > 48:
            context_parts.append(
                "Long average holding time - consider tighter exit conditions"
            )

        if not context_parts:
            context_parts.append("No significant issues detected - strategy performing within parameters")

        return "; ".join(context_parts)

    def generate_report(self, trades_file: str = "logs/trades.json") -> AnalysisReport:
        """
        Generate complete analysis report.

        Args:
            trades_file: Path to trades JSON file

        Returns:
            Complete analysis report
        """
        from uuid import uuid4

        # Gather all data
        market = self.get_market_condition()
        todays_trades = self.get_todays_trades(trades_file)
        performance = self.calculate_recent_performance(trades_file)
        context = self.generate_recommendations_context(market, performance)

        # Build strategy dict
        strategy_dict = {
            "symbol": self.config.symbol,
            "rsi_period": self.config.rsi_period,
            "rsi_oversold": self.config.rsi_oversold,
            "rsi_overbought": self.config.rsi_overbought,
            "sma_period": self.config.sma_period,
            "stop_loss_pct": self.config.stop_loss_pct,
            "position_size_pct": self.config.position_size_pct,
            "cash_reserve_pct": self.config.cash_reserve_pct,
        }

        report = AnalysisReport(
            report_id=str(uuid4()),
            generated_at=datetime.utcnow().isoformat(),
            strategy=strategy_dict,
            market_condition=asdict(market),
            todays_trades=[asdict(t) for t in todays_trades],
            recent_performance=asdict(performance),
            recommendations_context=context,
        )

        return report

    def save_report(self, report: AnalysisReport) -> Path:
        """
        Save report to file.

        Args:
            report: Analysis report to save

        Returns:
            Path to saved file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"analysis_{timestamp}.json"
        filepath = self.reports_dir / filename

        with open(filepath, "w") as f:
            f.write(report.to_json())

        logger.info(f"Report saved to {filepath}")
        return filepath

    def generate_and_save(self, trades_file: str = "logs/trades.json") -> tuple[AnalysisReport, Path]:
        """
        Generate and save analysis report.

        Args:
            trades_file: Path to trades JSON file

        Returns:
            Tuple of (report, filepath)
        """
        report = self.generate_report(trades_file)
        filepath = self.save_report(report)
        return report, filepath
