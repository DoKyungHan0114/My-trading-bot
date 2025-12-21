"""
Trading signal generation for RSI(2) Mean Reversion strategy.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd

from config.constants import SignalType
from config.settings import get_settings
from strategy.indicators import add_all_indicators

logger = logging.getLogger(__name__)


@dataclass
class Signal:
    """Trading signal with metadata."""
    timestamp: datetime
    signal_type: SignalType
    symbol: str
    price: float
    rsi: float
    reason: str
    strength: float = 1.0  # Signal strength 0-1

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "signal_type": self.signal_type.value,
            "symbol": self.symbol,
            "price": self.price,
            "rsi": self.rsi,
            "reason": self.reason,
            "strength": self.strength,
        }


class SignalGenerator:
    """Generate trading signals based on RSI(2) strategy."""

    def __init__(
        self,
        rsi_period: Optional[int] = None,
        rsi_oversold: Optional[float] = None,
        rsi_overbought: Optional[float] = None,
        sma_period: Optional[int] = None,
    ):
        """
        Initialize signal generator.

        Args:
            rsi_period: RSI calculation period
            rsi_oversold: RSI oversold threshold (entry)
            rsi_overbought: RSI overbought threshold (exit)
            sma_period: SMA period for trend filter
        """
        settings = get_settings()
        self.rsi_period = rsi_period or settings.strategy.rsi_period
        self.rsi_oversold = rsi_oversold or settings.strategy.rsi_oversold
        self.rsi_overbought = rsi_overbought or settings.strategy.rsi_overbought
        self.sma_period = sma_period or settings.strategy.sma_period
        self.symbol = settings.strategy.symbol

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data with required indicators.

        Args:
            df: Raw OHLCV DataFrame

        Returns:
            DataFrame with indicators
        """
        return add_all_indicators(
            df,
            rsi_period=self.rsi_period,
            sma_period=self.sma_period,
        )

    def generate_entry_signal(
        self,
        df: pd.DataFrame,
        has_position: bool = False,
    ) -> Optional[Signal]:
        """
        Check for entry (buy) signal.

        Entry conditions:
        1. Price above 200 SMA (uptrend)
        2. RSI(2) <= 10 (oversold)
        3. No current position

        Args:
            df: DataFrame with indicators (must call prepare_data first)
            has_position: Whether currently holding position

        Returns:
            Signal if entry conditions met, None otherwise
        """
        if has_position:
            return None

        if len(df) < self.sma_period:
            return None

        latest = df.iloc[-1]
        timestamp = df.index[-1]

        # Dynamic SMA column name
        sma_col = f"sma_{self.sma_period}"

        # Check if SMA is available
        if sma_col not in df.columns or pd.isna(latest[sma_col]):
            return None

        # Entry conditions (RSI only - SMA filter disabled for short-term mean reversion)
        rsi_oversold = latest["rsi"] <= self.rsi_oversold

        if rsi_oversold:
            # Calculate signal strength based on how oversold
            strength = min(1.0, (self.rsi_oversold - latest["rsi"]) / self.rsi_oversold + 0.5)

            reason = (
                f"RSI({self.rsi_period})={latest['rsi']:.1f} <= {self.rsi_oversold}, "
                f"Price ${latest['close']:.2f}"
            )

            logger.info(f"BUY signal generated: {reason}")

            return Signal(
                timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                signal_type=SignalType.BUY,
                symbol=self.symbol,
                price=latest["close"],
                rsi=latest["rsi"],
                reason=reason,
                strength=strength,
            )

        return None

    def generate_exit_signal(
        self,
        df: pd.DataFrame,
        entry_price: float,
        stop_loss_pct: float = 0.05,
    ) -> Optional[Signal]:
        """
        Check for exit (sell) signal.

        Exit conditions (any of):
        1. Close > previous day's high
        2. RSI(2) >= 70
        3. Price down 5% from entry (stop loss)

        Args:
            df: DataFrame with indicators
            entry_price: Entry price for stop loss calculation
            stop_loss_pct: Stop loss percentage

        Returns:
            Signal if exit conditions met, None otherwise
        """
        if len(df) < 2:
            return None

        latest = df.iloc[-1]
        timestamp = df.index[-1]

        # Exit condition 1: Close above previous high
        if not pd.isna(latest["prev_high"]) and latest["close"] > latest["prev_high"]:
            reason = f"Close ${latest['close']:.2f} > Previous High ${latest['prev_high']:.2f}"
            logger.info(f"SELL signal (prev high breakout): {reason}")

            return Signal(
                timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                signal_type=SignalType.SELL,
                symbol=self.symbol,
                price=latest["close"],
                rsi=latest["rsi"],
                reason=reason,
            )

        # Exit condition 2: RSI overbought
        if latest["rsi"] >= self.rsi_overbought:
            reason = f"RSI({self.rsi_period})={latest['rsi']:.1f} >= {self.rsi_overbought}"
            logger.info(f"SELL signal (RSI overbought): {reason}")

            return Signal(
                timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                signal_type=SignalType.SELL,
                symbol=self.symbol,
                price=latest["close"],
                rsi=latest["rsi"],
                reason=reason,
            )

        # Exit condition 3: Stop loss
        loss_pct = (latest["close"] - entry_price) / entry_price
        if loss_pct <= -stop_loss_pct:
            reason = f"Stop loss triggered: {loss_pct*100:.1f}% loss (threshold: -{stop_loss_pct*100}%)"
            logger.info(f"SELL signal (stop loss): {reason}")

            return Signal(
                timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                signal_type=SignalType.SELL,
                symbol=self.symbol,
                price=latest["close"],
                rsi=latest["rsi"],
                reason=reason,
                strength=0.0,  # Forced exit
            )

        return None

    def generate_signals(
        self,
        df: pd.DataFrame,
        has_position: bool = False,
        entry_price: Optional[float] = None,
        stop_loss_pct: float = 0.05,
    ) -> Optional[Signal]:
        """
        Generate trading signal based on current state.

        Args:
            df: DataFrame with OHLCV data (raw or with indicators)
            has_position: Whether currently holding position
            entry_price: Entry price if in position
            stop_loss_pct: Stop loss percentage

        Returns:
            Trading signal or None
        """
        # Ensure indicators are calculated
        if "rsi" not in df.columns:
            df = self.prepare_data(df)

        if has_position and entry_price is not None:
            return self.generate_exit_signal(df, entry_price, stop_loss_pct)
        else:
            return self.generate_entry_signal(df, has_position)
