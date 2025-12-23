"""
Market regime classifier for RAG metadata.
Classifies market conditions into discrete regimes for better pattern matching.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from data.fetcher import DataFetcher


class MarketRegime(Enum):
    """Market regime classifications."""
    BULL_LOW_VOL = "BULL_LOW_VOL"      # Uptrend, low volatility
    BULL_HIGH_VOL = "BULL_HIGH_VOL"    # Uptrend, high volatility
    BEAR_LOW_VOL = "BEAR_LOW_VOL"      # Downtrend, low volatility
    BEAR_HIGH_VOL = "BEAR_HIGH_VOL"    # Downtrend, high volatility (crash)
    SIDEWAYS = "SIDEWAYS"              # No clear trend


class VolatilityLevel(Enum):
    """Volatility classifications."""
    LOW = "LOW"        # Bottom 33%
    MEDIUM = "MEDIUM"  # Middle 33%
    HIGH = "HIGH"      # Top 33%


class TrendDirection(Enum):
    """Trend direction."""
    UP = "UP"
    DOWN = "DOWN"
    NEUTRAL = "NEUTRAL"


@dataclass
class MarketCondition:
    """Complete market condition snapshot."""
    regime: MarketRegime
    trend: TrendDirection
    volatility: VolatilityLevel

    # Numeric values
    avg_rsi: float
    atr_value: float
    atr_percentile: float  # 0-100, where we stand vs history

    # Price action
    period_return: float  # % return during period
    max_drawdown: float   # Max drawdown during period

    # Trend indicators
    price_vs_sma20: float  # % above/below SMA20
    sma20_vs_sma50: float  # % difference

    def to_dict(self) -> dict:
        """Convert to dictionary for Firestore."""
        return {
            "regime": self.regime.value,
            "trend": self.trend.value,
            "volatility": self.volatility.value,
            "avg_rsi": round(self.avg_rsi, 2),
            "atr_value": round(self.atr_value, 4),
            "atr_percentile": round(self.atr_percentile, 1),
            "period_return": round(self.period_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "price_vs_sma20": round(self.price_vs_sma20, 2),
            "sma20_vs_sma50": round(self.sma20_vs_sma50, 2),
        }

    def to_embedding_text(self) -> str:
        """Convert to text for embedding."""
        return (
            f"Market regime: {self.regime.value}. "
            f"Trend: {self.trend.value}. "
            f"Volatility: {self.volatility.value}. "
            f"RSI average: {self.avg_rsi:.1f}. "
            f"ATR percentile: {self.atr_percentile:.0f}%. "
            f"Period return: {self.period_return:+.1f}%. "
            f"Price vs SMA20: {self.price_vs_sma20:+.1f}%."
        )


class RegimeClassifier:
    """Classify market regimes from price data."""

    def __init__(self):
        self.fetcher = DataFetcher()

    def classify(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        lookback_days: int = 60,
    ) -> Optional[MarketCondition]:
        """
        Classify market conditions for a given period.

        Args:
            symbol: Stock symbol
            start_date: Period start (YYYY-MM-DD)
            end_date: Period end (YYYY-MM-DD)
            lookback_days: Days of history for context

        Returns:
            MarketCondition or None if insufficient data
        """
        # Fetch extended data for context
        from datetime import datetime, timedelta

        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        extended_start = (start_dt - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        df = self.fetcher.get_daily_bars(symbol, extended_start, end_date)

        if len(df) < 30:
            return None

        # Add indicators
        df = self._add_indicators(df)

        # Get the target period
        period_df = df[df.index >= start_date]

        if len(period_df) < 2:
            return None

        # Calculate metrics
        avg_rsi = period_df["rsi"].mean()
        atr_value = period_df["atr"].iloc[-1]

        # ATR percentile vs history
        historical_atr = df["atr"].dropna()
        atr_percentile = (historical_atr < atr_value).sum() / len(historical_atr) * 100

        # Period return
        period_return = (period_df["close"].iloc[-1] / period_df["close"].iloc[0] - 1) * 100

        # Max drawdown
        cummax = period_df["close"].cummax()
        drawdown = (period_df["close"] - cummax) / cummax * 100
        max_drawdown = drawdown.min()

        # Price vs SMA20
        price_vs_sma20 = (period_df["close"].iloc[-1] / period_df["sma20"].iloc[-1] - 1) * 100

        # SMA20 vs SMA50
        sma20_vs_sma50 = (period_df["sma20"].iloc[-1] / period_df["sma50"].iloc[-1] - 1) * 100

        # Classify trend
        trend = self._classify_trend(period_df, sma20_vs_sma50)

        # Classify volatility
        volatility = self._classify_volatility(atr_percentile)

        # Classify regime
        regime = self._classify_regime(trend, volatility, period_return)

        return MarketCondition(
            regime=regime,
            trend=trend,
            volatility=volatility,
            avg_rsi=avg_rsi,
            atr_value=atr_value,
            atr_percentile=atr_percentile,
            period_return=period_return,
            max_drawdown=max_drawdown,
            price_vs_sma20=price_vs_sma20,
            sma20_vs_sma50=sma20_vs_sma50,
        )

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicators to dataframe."""
        df = df.copy()

        # RSI
        delta = df["close"].diff()
        gain = delta.where(delta > 0, 0).rolling(window=2).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=2).mean()
        rs = gain / loss.replace(0, np.inf)
        df["rsi"] = 100 - (100 / (1 + rs))

        # ATR
        high_low = df["high"] - df["low"]
        high_close = (df["high"] - df["close"].shift()).abs()
        low_close = (df["low"] - df["close"].shift()).abs()
        tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
        df["atr"] = tr.rolling(window=14).mean()

        # SMAs
        df["sma20"] = df["close"].rolling(window=20).mean()
        df["sma50"] = df["close"].rolling(window=50).mean()

        return df

    def _classify_trend(self, df: pd.DataFrame, sma20_vs_sma50: float) -> TrendDirection:
        """Classify trend direction."""
        # Price movement during period
        price_change = (df["close"].iloc[-1] / df["close"].iloc[0] - 1) * 100

        # SMA alignment
        if sma20_vs_sma50 > 2 and price_change > 1:
            return TrendDirection.UP
        elif sma20_vs_sma50 < -2 and price_change < -1:
            return TrendDirection.DOWN
        else:
            return TrendDirection.NEUTRAL

    def _classify_volatility(self, atr_percentile: float) -> VolatilityLevel:
        """Classify volatility level."""
        if atr_percentile < 33:
            return VolatilityLevel.LOW
        elif atr_percentile < 67:
            return VolatilityLevel.MEDIUM
        else:
            return VolatilityLevel.HIGH

    def _classify_regime(
        self,
        trend: TrendDirection,
        volatility: VolatilityLevel,
        period_return: float,
    ) -> MarketRegime:
        """Classify overall market regime."""
        is_high_vol = volatility == VolatilityLevel.HIGH

        if trend == TrendDirection.UP:
            return MarketRegime.BULL_HIGH_VOL if is_high_vol else MarketRegime.BULL_LOW_VOL
        elif trend == TrendDirection.DOWN:
            return MarketRegime.BEAR_HIGH_VOL if is_high_vol else MarketRegime.BEAR_LOW_VOL
        else:
            # Sideways - check if it's volatile sideways
            if abs(period_return) < 3:
                return MarketRegime.SIDEWAYS
            elif period_return > 0:
                return MarketRegime.BULL_HIGH_VOL if is_high_vol else MarketRegime.BULL_LOW_VOL
            else:
                return MarketRegime.BEAR_HIGH_VOL if is_high_vol else MarketRegime.BEAR_LOW_VOL


if __name__ == "__main__":
    # Test the classifier
    classifier = RegimeClassifier()

    test_periods = [
        ("2024-09-01", "2024-09-08"),  # Known crash
        ("2024-11-01", "2024-11-08"),  # Known rally
        ("2024-03-01", "2024-03-08"),  # Normal
    ]

    for start, end in test_periods:
        condition = classifier.classify("TQQQ", start, end)
        if condition:
            print(f"\n{start} ~ {end}:")
            print(f"  Regime: {condition.regime.value}")
            print(f"  Return: {condition.period_return:+.2f}%")
            print(f"  ATR%: {condition.atr_percentile:.0f}")
            print(f"  Embedding: {condition.to_embedding_text()}")
