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
    # Additional indicator values for trade review
    vwap: Optional[float] = None
    sma: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None

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
            "vwap": self.vwap,
            "sma": self.sma,
            "day_high": self.day_high,
            "day_low": self.day_low,
        }


class SignalGenerator:
    """Generate trading signals based on RSI(2) strategy with multi-indicator filters."""

    def __init__(
        self,
        rsi_period: Optional[int] = None,
        rsi_oversold: Optional[float] = None,
        rsi_overbought: Optional[float] = None,
        sma_period: Optional[int] = None,
        # VWAP Filter
        vwap_filter_enabled: Optional[bool] = None,
        vwap_entry_below: Optional[bool] = None,
        # Bollinger Bands Filter
        bb_filter_enabled: Optional[bool] = None,
        bb_period: Optional[int] = None,
        bb_std_dev: Optional[float] = None,
        # Volume Filter
        volume_filter_enabled: Optional[bool] = None,
        volume_min_ratio: Optional[float] = None,
        volume_avg_period: Optional[int] = None,
        # Short Selling
        short_enabled: Optional[bool] = None,
        rsi_overbought_short: Optional[float] = None,
        rsi_oversold_short: Optional[float] = None,
    ):
        """
        Initialize signal generator with multi-indicator support.

        Args:
            rsi_period: RSI calculation period
            rsi_oversold: RSI oversold threshold (long entry)
            rsi_overbought: RSI overbought threshold (long exit)
            sma_period: SMA period for trend filter
            vwap_filter_enabled: Enable VWAP filter
            vwap_entry_below: Enter only below VWAP
            bb_filter_enabled: Enable Bollinger Bands filter
            bb_period: Bollinger Bands period
            bb_std_dev: Bollinger Bands standard deviation
            volume_filter_enabled: Enable volume filter
            volume_min_ratio: Minimum volume ratio vs average
            volume_avg_period: Volume average period
            short_enabled: Enable short selling
            rsi_overbought_short: RSI overbought threshold for short entry
            rsi_oversold_short: RSI oversold threshold for short exit
        """
        settings = get_settings()
        # Core parameters
        self.rsi_period = rsi_period or settings.strategy.rsi_period
        self.rsi_oversold = rsi_oversold or settings.strategy.rsi_oversold
        self.rsi_overbought = rsi_overbought or settings.strategy.rsi_overbought
        self.sma_period = sma_period or settings.strategy.sma_period
        self.symbol = settings.strategy.symbol
        # VWAP Filter
        self.vwap_filter_enabled = vwap_filter_enabled if vwap_filter_enabled is not None else settings.strategy.vwap_filter_enabled
        self.vwap_entry_below = vwap_entry_below if vwap_entry_below is not None else settings.strategy.vwap_entry_below
        # Bollinger Bands Filter
        self.bb_filter_enabled = bb_filter_enabled if bb_filter_enabled is not None else settings.strategy.bb_filter_enabled
        self.bb_period = bb_period or settings.strategy.bb_period
        self.bb_std_dev = bb_std_dev or settings.strategy.bb_std_dev
        # Volume Filter
        self.volume_filter_enabled = volume_filter_enabled if volume_filter_enabled is not None else settings.strategy.volume_filter_enabled
        self.volume_min_ratio = volume_min_ratio or settings.strategy.volume_min_ratio
        self.volume_avg_period = volume_avg_period or settings.strategy.volume_avg_period
        # Inverse/Hedge Trading (SQQQ)
        self.short_enabled = short_enabled if short_enabled is not None else settings.strategy.short_enabled
        self.inverse_symbol = settings.strategy.inverse_symbol
        self.use_inverse_etf = settings.strategy.use_inverse_etf
        self.rsi_overbought_short = rsi_overbought_short or settings.strategy.rsi_overbought_short
        self.rsi_oversold_short = rsi_oversold_short or settings.strategy.rsi_oversold_short

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Prepare data with all required indicators.

        Args:
            df: Raw OHLCV DataFrame

        Returns:
            DataFrame with indicators
        """
        return add_all_indicators(
            df,
            rsi_period=self.rsi_period,
            sma_period=self.sma_period,
            bb_period=self.bb_period,
            bb_std_dev=self.bb_std_dev,
            volume_avg_period=self.volume_avg_period,
        )

    def generate_entry_signal(
        self,
        df: pd.DataFrame,
        has_position: bool = False,
    ) -> Optional[Signal]:
        """
        Check for entry (buy) signal with multi-indicator filtering.

        Entry conditions:
        1. RSI(2) <= oversold threshold (required)
        2. If VWAP filter enabled: price below/above VWAP
        3. If BB filter enabled: price at or below lower band
        4. If Volume filter enabled: volume ratio >= threshold

        Args:
            df: DataFrame with indicators (must call prepare_data first)
            has_position: Whether currently holding position

        Returns:
            Signal if entry conditions met, None otherwise
        """
        if has_position:
            return None

        min_period = max(self.sma_period, self.bb_period, self.volume_avg_period)
        if len(df) < min_period:
            return None

        latest = df.iloc[-1]
        timestamp = df.index[-1]

        # Dynamic SMA column name
        sma_col = f"sma_{self.sma_period}"

        # Check if SMA is available
        if sma_col not in df.columns or pd.isna(latest[sma_col]):
            return None

        # Required: RSI oversold
        if latest["rsi"] > self.rsi_oversold:
            return None

        # Track filter status for reason string
        filters_passed = []

        # VWAP Filter
        if self.vwap_filter_enabled:
            if "vwap" in df.columns and pd.notna(latest.get("vwap")):
                if self.vwap_entry_below:
                    if latest["close"] >= latest["vwap"]:
                        return None  # Price must be below VWAP
                    filters_passed.append(f"VWAP(below ${latest['vwap']:.2f})")
                else:
                    if latest["close"] <= latest["vwap"]:
                        return None  # Price must be above VWAP
                    filters_passed.append(f"VWAP(above ${latest['vwap']:.2f})")

        # Bollinger Bands Filter
        if self.bb_filter_enabled:
            if "bb_lower" in df.columns and pd.notna(latest.get("bb_lower")):
                if latest["close"] > latest["bb_lower"]:
                    return None  # Price must be at or below lower band
                filters_passed.append(f"BB(lower ${latest['bb_lower']:.2f})")

        # Volume Filter
        if self.volume_filter_enabled:
            if "volume_ratio" in df.columns and pd.notna(latest.get("volume_ratio")):
                if latest["volume_ratio"] < self.volume_min_ratio:
                    return None  # Volume too low
                filters_passed.append(f"Vol({latest['volume_ratio']:.1f}x)")

        # All filters passed - generate signal
        strength = min(1.0, (self.rsi_oversold - latest["rsi"]) / self.rsi_oversold + 0.5)

        filter_str = ", ".join(filters_passed) if filters_passed else "RSI only"
        reason = (
            f"RSI({self.rsi_period})={latest['rsi']:.1f} <= {self.rsi_oversold}, "
            f"Price ${latest['close']:.2f}, Filters: [{filter_str}]"
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
            vwap=latest.get("vwap") if "vwap" in latest else None,
            sma=latest.get("sma") if "sma" in latest else None,
            day_high=latest.get("high"),
            day_low=latest.get("low"),
        )

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

        # Helper to get indicator values
        def get_indicators():
            return {
                "vwap": latest.get("vwap") if "vwap" in latest else None,
                "sma": latest.get("sma") if "sma" in latest else None,
                "day_high": latest.get("high"),
                "day_low": latest.get("low"),
            }

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
                **get_indicators(),
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
                **get_indicators(),
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
                **get_indicators(),
            )

        return None

    def generate_short_entry_signal(
        self,
        df: pd.DataFrame,
        has_position: bool = False,
    ) -> Optional[Signal]:
        """
        Check for hedge/short entry signal.

        When use_inverse_etf=True: Buy SQQQ (inverse ETF) instead of shorting TQQQ
        When use_inverse_etf=False: Short TQQQ directly

        Entry conditions:
        1. RSI(2) >= rsi_overbought_short (e.g., 90 - very conservative)
        2. Price above SMA (trend is extended)
        3. If VWAP filter enabled: price above VWAP (overextended)

        Args:
            df: DataFrame with indicators
            has_position: Whether currently holding any position

        Returns:
            Signal if hedge/short entry conditions met, None otherwise
        """
        if not self.short_enabled:
            return None

        if has_position:
            return None

        min_period = max(self.sma_period, self.bb_period, self.volume_avg_period)
        if len(df) < min_period:
            return None

        latest = df.iloc[-1]
        timestamp = df.index[-1]

        sma_col = f"sma_{self.sma_period}"

        if sma_col not in df.columns or pd.isna(latest[sma_col]):
            return None

        # Required: RSI overbought for hedge
        if latest["rsi"] < self.rsi_overbought_short:
            return None

        # Required: Price above SMA (trend is extended upward)
        if latest["close"] <= latest[sma_col]:
            return None

        filters_passed = []

        # VWAP Filter - enter when price is ABOVE VWAP (overextended)
        if self.vwap_filter_enabled:
            if "vwap" in df.columns and pd.notna(latest.get("vwap")):
                if latest["close"] <= latest["vwap"]:
                    return None
                filters_passed.append(f"VWAP(above ${latest['vwap']:.2f})")

        # Bollinger Bands Filter - price at or above upper band
        if self.bb_filter_enabled:
            if "bb_upper" in df.columns and pd.notna(latest.get("bb_upper")):
                if latest["close"] < latest["bb_upper"]:
                    return None
                filters_passed.append(f"BB(upper ${latest['bb_upper']:.2f})")

        # Volume Filter
        if self.volume_filter_enabled:
            if "volume_ratio" in df.columns and pd.notna(latest.get("volume_ratio")):
                if latest["volume_ratio"] < self.volume_min_ratio:
                    return None
                filters_passed.append(f"Vol({latest['volume_ratio']:.1f}x)")

        # Calculate signal strength
        strength = min(1.0, (latest["rsi"] - self.rsi_overbought_short) / (100 - self.rsi_overbought_short) + 0.5)

        filter_str = ", ".join(filters_passed) if filters_passed else "RSI only"

        # Use HEDGE_BUY for inverse ETF, SHORT for direct shorting
        if self.use_inverse_etf:
            signal_type = SignalType.HEDGE_BUY
            target_symbol = self.inverse_symbol
            reason = (
                f"HEDGE(SQQQ): TQQQ RSI({self.rsi_period})={latest['rsi']:.1f} >= {self.rsi_overbought_short}, "
                f"Price ${latest['close']:.2f} > SMA ${latest[sma_col]:.2f}, Filters: [{filter_str}]"
            )
            logger.info(f"HEDGE_BUY signal generated: Buy {target_symbol} - {reason}")
        else:
            signal_type = SignalType.SHORT
            target_symbol = self.symbol
            reason = (
                f"SHORT: RSI({self.rsi_period})={latest['rsi']:.1f} >= {self.rsi_overbought_short}, "
                f"Price ${latest['close']:.2f} > SMA ${latest[sma_col]:.2f}, Filters: [{filter_str}]"
            )
            logger.info(f"SHORT signal generated: {reason}")

        return Signal(
            timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
            signal_type=signal_type,
            symbol=target_symbol,
            price=latest["close"],
            rsi=latest["rsi"],
            reason=reason,
            strength=strength,
            vwap=latest.get("vwap") if "vwap" in latest else None,
            sma=latest.get(sma_col) if sma_col in latest else None,
            day_high=latest.get("high"),
            day_low=latest.get("low"),
        )

    def generate_short_exit_signal(
        self,
        df: pd.DataFrame,
        entry_price: float,
        stop_loss_pct: float = 0.02,
        is_hedge: bool = False,
        hedge_entry_price: float = 0.0,
        current_hedge_price: Optional[float] = None,
    ) -> Optional[Signal]:
        """
        Check for hedge/short exit signal.

        When use_inverse_etf=True: Sell SQQQ (hedge exit)
        When use_inverse_etf=False: Cover TQQQ short

        Exit conditions (any of):
        1. RSI(2) <= rsi_oversold_short (mean reversion complete)
        2. Stop loss triggered
        3. Close below previous day's low (for shorts)

        Args:
            df: DataFrame with indicators (TQQQ data)
            entry_price: TQQQ entry price (for RSI-based shorts)
            stop_loss_pct: Stop loss percentage
            is_hedge: Whether this is a hedge position (SQQQ)
            hedge_entry_price: SQQQ entry price for stop loss calculation
            current_hedge_price: Current SQQQ price for stop loss check

        Returns:
            Signal if exit conditions met, None otherwise
        """
        if len(df) < 2:
            return None

        latest = df.iloc[-1]
        timestamp = df.index[-1]

        # Determine signal type and symbol based on position type
        if is_hedge or self.use_inverse_etf:
            signal_type = SignalType.HEDGE_SELL
            target_symbol = self.inverse_symbol
            exit_label = "HEDGE_SELL"
        else:
            signal_type = SignalType.COVER
            target_symbol = self.symbol
            exit_label = "COVER"

        # Helper to get indicator values
        def get_indicators():
            return {
                "vwap": latest.get("vwap") if "vwap" in latest else None,
                "sma": latest.get("sma") if "sma" in latest else None,
                "day_high": latest.get("high"),
                "day_low": latest.get("low"),
            }

        # Exit condition 1: RSI oversold (mean reversion complete)
        if latest["rsi"] <= self.rsi_oversold_short:
            reason = f"{exit_label}: TQQQ RSI({self.rsi_period})={latest['rsi']:.1f} <= {self.rsi_oversold_short}"
            logger.info(f"{exit_label} signal (RSI target): {reason}")

            return Signal(
                timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                signal_type=signal_type,
                symbol=target_symbol,
                price=current_hedge_price if is_hedge and current_hedge_price else latest["close"],
                rsi=latest["rsi"],
                reason=reason,
                **get_indicators(),
            )

        # Exit condition 2: Stop loss
        if is_hedge and hedge_entry_price > 0 and current_hedge_price is not None:
            # For SQQQ hedge: stop loss if SQQQ price drops (using actual SQQQ price)
            loss_pct = (hedge_entry_price - current_hedge_price) / hedge_entry_price
            if loss_pct >= stop_loss_pct:
                reason = f"{exit_label}: Stop loss triggered: -{loss_pct*100:.1f}% on SQQQ (threshold: -{stop_loss_pct*100}%)"
                logger.info(f"{exit_label} signal (stop loss): {reason}")
                return Signal(
                    timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                    signal_type=signal_type,
                    symbol=target_symbol,
                    price=current_hedge_price,
                    rsi=latest["rsi"],
                    reason=reason,
                    strength=0.0,
                    **get_indicators(),
                )
        elif not is_hedge:
            # For direct short: stop loss if TQQQ price rises
            loss_pct = (latest["close"] - entry_price) / entry_price
            if loss_pct >= stop_loss_pct:
                reason = f"{exit_label}: Stop loss triggered: +{loss_pct*100:.1f}% move against short (threshold: +{stop_loss_pct*100}%)"
                logger.info(f"{exit_label} signal (stop loss): {reason}")
                return Signal(
                    timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                    signal_type=signal_type,
                    symbol=target_symbol,
                    price=latest["close"],
                    rsi=latest["rsi"],
                    reason=reason,
                    strength=0.0,
                    **get_indicators(),
                )

        # Exit condition 3: Momentum shift (for direct shorts only)
        if not is_hedge:
            if "prev_low" in df.columns and not pd.isna(latest.get("prev_low")):
                if latest["close"] < latest["prev_low"]:
                    reason = f"{exit_label}: Close ${latest['close']:.2f} < Previous Low ${latest['prev_low']:.2f}"
                    logger.info(f"{exit_label} signal (momentum shift): {reason}")
                    return Signal(
                        timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                        signal_type=signal_type,
                        symbol=target_symbol,
                        price=latest["close"],
                        rsi=latest["rsi"],
                        reason=reason,
                        **get_indicators(),
                    )

        return None

    def generate_signals(
        self,
        df: pd.DataFrame,
        has_position: bool = False,
        entry_price: Optional[float] = None,
        stop_loss_pct: float = 0.05,
        position_side: Optional[str] = None,
        short_stop_loss_pct: Optional[float] = None,
        hedge_entry_price: Optional[float] = None,
        current_hedge_price: Optional[float] = None,
    ) -> Optional[Signal]:
        """
        Generate trading signal based on current state.

        Args:
            df: DataFrame with OHLCV data (raw or with indicators)
            has_position: Whether currently holding position
            entry_price: Entry price if in position (TQQQ price)
            stop_loss_pct: Stop loss percentage for long positions
            position_side: "long", "short", or "hedge" if in position
            short_stop_loss_pct: Stop loss percentage for short/hedge positions
            hedge_entry_price: SQQQ entry price for hedge stop loss calculation
            current_hedge_price: Current SQQQ price for hedge stop loss check

        Returns:
            Trading signal or None
        """
        # Ensure indicators are calculated
        if "rsi" not in df.columns:
            df = self.prepare_data(df)

        settings = get_settings()
        short_sl = short_stop_loss_pct or settings.strategy.short_stop_loss_pct

        if has_position and entry_price is not None:
            if position_side == "hedge":
                # Hedge position: SQQQ long
                return self.generate_short_exit_signal(
                    df, entry_price, short_sl,
                    is_hedge=True,
                    hedge_entry_price=hedge_entry_price or 0.0,
                    current_hedge_price=current_hedge_price,
                )
            elif position_side == "short":
                # Direct short position: TQQQ short
                return self.generate_short_exit_signal(df, entry_price, short_sl, is_hedge=False)
            else:
                # Long position: TQQQ long
                return self.generate_exit_signal(df, entry_price, stop_loss_pct)
        else:
            # Try long entry first, then hedge/short
            long_signal = self.generate_entry_signal(df, has_position)
            if long_signal:
                return long_signal

            # Try hedge/short entry if enabled
            if self.short_enabled:
                return self.generate_short_entry_signal(df, has_position)

            return None
