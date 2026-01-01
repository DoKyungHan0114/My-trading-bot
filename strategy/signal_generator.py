"""
Refactored Signal Generator with modular filter system.

This is the new implementation that uses composable filters.
The original signals.py is preserved for backward compatibility.
"""
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List

import pandas as pd

from config.constants import SignalType
from config.settings import get_settings
from strategy.indicators import add_all_indicators
from strategy.filters.base import SignalFilter, FilterResult
from strategy.filters.rsi_filter import RSIFilter
from strategy.filters.vwap_filter import VWAPFilter
from strategy.filters.bollinger_filter import BollingerBandsFilter
from strategy.filters.volume_filter import VolumeFilter
from strategy.filters.sma_filter import SMAFilter
from strategy.filters.stop_loss_filter import StopLossFilter, PreviousHighLowFilter

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
    strength: float = 1.0
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


class FilterChain:
    """
    Chain of filters that must all pass for a signal.

    Filters are evaluated in order and short-circuit on first failure.
    """

    def __init__(self, filters: Optional[List[SignalFilter]] = None):
        self._filters: List[SignalFilter] = filters or []

    def add(self, filter: SignalFilter) -> "FilterChain":
        """Add a filter to the chain."""
        self._filters.append(filter)
        return self

    def remove(self, filter_type: type) -> "FilterChain":
        """Remove all filters of a given type."""
        self._filters = [f for f in self._filters if not isinstance(f, filter_type)]
        return self

    def check_all(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        check_method: str,
        entry_price: float = 0.0,
    ) -> tuple[bool, List[str]]:
        """
        Run all filters and collect results.

        Args:
            df: Full DataFrame
            bar: Current bar
            check_method: Method to call on each filter
            entry_price: Entry price for exit checks

        Returns:
            Tuple of (all_passed, list_of_reasons)
        """
        passed_reasons: List[str] = []
        all_passed = True

        for filter in self._filters:
            if not filter.enabled:
                continue

            method = getattr(filter, check_method)

            if "exit" in check_method:
                result = method(df, bar, entry_price)
            else:
                result = method(df, bar)

            if not result.passed:
                all_passed = False
                break

            if result.reason and "[skipped" not in result.reason:
                passed_reasons.append(result.reason)

        return all_passed, passed_reasons

    @property
    def filters(self) -> List[SignalFilter]:
        return self._filters


class ModularSignalGenerator:
    """
    Signal generator with modular, composable filters.

    This replaces the monolithic SignalGenerator with a more flexible design.
    Each filter can be enabled/disabled and configured independently.
    """

    def __init__(
        self,
        # Core parameters
        symbol: Optional[str] = None,
        inverse_symbol: Optional[str] = None,
        use_inverse_etf: bool = True,
        short_enabled: bool = False,
        # Filter instances (optional - will create defaults if not provided)
        rsi_filter: Optional[RSIFilter] = None,
        vwap_filter: Optional[VWAPFilter] = None,
        bb_filter: Optional[BollingerBandsFilter] = None,
        volume_filter: Optional[VolumeFilter] = None,
        sma_filter: Optional[SMAFilter] = None,
        stop_loss_filter: Optional[StopLossFilter] = None,
        prev_hl_filter: Optional[PreviousHighLowFilter] = None,
    ):
        settings = get_settings()
        strategy = settings.strategy

        # Core settings
        self.symbol = symbol or strategy.symbol
        self.inverse_symbol = inverse_symbol or strategy.inverse_symbol
        self.use_inverse_etf = use_inverse_etf
        self.short_enabled = short_enabled if short_enabled is not None else strategy.short_enabled

        # Initialize filters with settings defaults
        self.rsi_filter = rsi_filter or RSIFilter(
            period=strategy.rsi_period,
            oversold=strategy.rsi_oversold,
            overbought=strategy.rsi_overbought,
            overbought_short=strategy.rsi_overbought_short,
            oversold_short=strategy.rsi_oversold_short,
            enabled=True,
        )

        self.vwap_filter = vwap_filter or VWAPFilter(
            entry_below=strategy.vwap_entry_below,
            enabled=strategy.vwap_filter_enabled,
        )

        self.bb_filter = bb_filter or BollingerBandsFilter(
            period=strategy.bb_period,
            std_dev=strategy.bb_std_dev,
            enabled=strategy.bb_filter_enabled,
        )

        self.volume_filter = volume_filter or VolumeFilter(
            min_ratio=strategy.volume_min_ratio,
            avg_period=strategy.volume_avg_period,
            enabled=strategy.volume_filter_enabled,
        )

        self.sma_filter = sma_filter or SMAFilter(
            period=strategy.sma_period,
            enabled=True,
        )

        self.stop_loss_filter = stop_loss_filter or StopLossFilter(
            stop_loss_pct=strategy.stop_loss_pct,
            atr_multiplier=strategy.atr_stop_multiplier,
            use_atr=strategy.atr_stop_enabled,
            enabled=True,
        )

        self.prev_hl_filter = prev_hl_filter or PreviousHighLowFilter(enabled=True)

        # Build filter chains
        self._entry_chain = FilterChain([
            self.rsi_filter,
            self.sma_filter,
            self.vwap_filter,
            self.bb_filter,
            self.volume_filter,
        ])

        self._exit_chain = FilterChain([
            self.rsi_filter,
            self.stop_loss_filter,
            self.prev_hl_filter,
        ])

        self._short_entry_chain = FilterChain([
            self.rsi_filter,
            self.sma_filter,
            self.vwap_filter,
            self.bb_filter,
            self.volume_filter,
        ])

        self._short_exit_chain = FilterChain([
            self.rsi_filter,
            self.stop_loss_filter,
            self.prev_hl_filter,
        ])

    def prepare_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Prepare data with all required indicators."""
        settings = get_settings()
        return add_all_indicators(
            df,
            rsi_period=self.rsi_filter.period,
            sma_period=self.sma_filter.period,
            bb_period=self.bb_filter.period,
            bb_std_dev=self.bb_filter.std_dev,
            volume_avg_period=self.volume_filter.avg_period,
        )

    def generate_entry_signal(
        self,
        df: pd.DataFrame,
        has_position: bool = False,
    ) -> Optional[Signal]:
        """Check for long entry signal."""
        if has_position:
            return None

        min_period = max(
            self.sma_filter.period,
            self.bb_filter.period,
            self.volume_filter.avg_period,
        )
        if len(df) < min_period:
            return None

        bar = df.iloc[-1]
        timestamp = df.index[-1]

        # Check RSI first (required)
        rsi_result = self.rsi_filter.check_long_entry(df, bar)
        if not rsi_result:
            return None

        # Check other filters
        filters_passed = [rsi_result.reason]

        for filter in [self.vwap_filter, self.bb_filter, self.volume_filter]:
            if not filter.enabled:
                continue
            result = filter.check_long_entry(df, bar)
            if not result.passed:
                return None
            if result.reason and "[skipped" not in result.reason:
                filters_passed.append(result.reason)

        # All filters passed - generate signal
        strength = self.rsi_filter.calculate_strength(bar["rsi"], for_long=True)
        filter_str = ", ".join(filters_passed[1:]) if len(filters_passed) > 1 else "RSI only"

        reason = (
            f"{filters_passed[0]}, "
            f"Price ${bar['close']:.2f}, Filters: [{filter_str}]"
        )

        logger.info(f"BUY signal generated: {reason}")

        return Signal(
            timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
            signal_type=SignalType.BUY,
            symbol=self.symbol,
            price=bar["close"],
            rsi=bar["rsi"],
            reason=reason,
            strength=strength,
            vwap=bar.get("vwap") if "vwap" in bar else None,
            sma=bar.get(f"sma_{self.sma_filter.period}"),
            day_high=bar.get("high"),
            day_low=bar.get("low"),
        )

    def generate_exit_signal(
        self,
        df: pd.DataFrame,
        entry_price: float,
        stop_loss_pct: float = 0.05,
    ) -> Optional[Signal]:
        """Check for long exit signal."""
        if len(df) < 2:
            return None

        bar = df.iloc[-1]
        timestamp = df.index[-1]

        def create_signal(reason: str, strength: float = 1.0) -> Signal:
            return Signal(
                timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                signal_type=SignalType.SELL,
                symbol=self.symbol,
                price=bar["close"],
                rsi=bar.get("rsi", 0),
                reason=reason,
                strength=strength,
                vwap=bar.get("vwap"),
                sma=bar.get(f"sma_{self.sma_filter.period}"),
                day_high=bar.get("high"),
                day_low=bar.get("low"),
            )

        # Check previous high breakout
        prev_hl_result = self.prev_hl_filter.check_long_exit(df, bar, entry_price)
        if prev_hl_result.passed:
            logger.info(f"SELL signal (prev high breakout): {prev_hl_result.reason}")
            return create_signal(prev_hl_result.reason)

        # Check RSI overbought
        rsi_result = self.rsi_filter.check_long_exit(df, bar, entry_price)
        if rsi_result.passed:
            logger.info(f"SELL signal (RSI overbought): {rsi_result.reason}")
            return create_signal(rsi_result.reason)

        # Check stop loss
        self.stop_loss_filter.stop_loss_pct = stop_loss_pct
        sl_result = self.stop_loss_filter.check_long_exit(df, bar, entry_price)
        if sl_result.passed:
            logger.info(f"SELL signal (stop loss): {sl_result.reason}")
            return create_signal(sl_result.reason, strength=0.0)

        return None

    def generate_short_entry_signal(
        self,
        df: pd.DataFrame,
        has_position: bool = False,
    ) -> Optional[Signal]:
        """Check for short/hedge entry signal."""
        if not self.short_enabled or has_position:
            return None

        min_period = max(
            self.sma_filter.period,
            self.bb_filter.period,
            self.volume_filter.avg_period,
        )
        if len(df) < min_period:
            return None

        bar = df.iloc[-1]
        timestamp = df.index[-1]

        # Check RSI overbought for short
        rsi_result = self.rsi_filter.check_short_entry(df, bar)
        if not rsi_result:
            return None

        # Check SMA - price must be above for short (overextended)
        sma_result = self.sma_filter.check_short_entry(df, bar)
        if not sma_result:
            return None

        # Check other filters
        filters_passed = [rsi_result.reason]

        for filter in [self.vwap_filter, self.bb_filter, self.volume_filter]:
            if not filter.enabled:
                continue
            result = filter.check_short_entry(df, bar)
            if not result.passed:
                return None
            if result.reason and "[skipped" not in result.reason:
                filters_passed.append(result.reason)

        # Determine signal type
        strength = self.rsi_filter.calculate_strength(bar["rsi"], for_long=False)
        filter_str = ", ".join(filters_passed[1:]) if len(filters_passed) > 1 else "RSI only"

        if self.use_inverse_etf:
            signal_type = SignalType.HEDGE_BUY
            target_symbol = self.inverse_symbol
            reason = (
                f"HEDGE(SQQQ): TQQQ {filters_passed[0]}, "
                f"Price ${bar['close']:.2f} > SMA, Filters: [{filter_str}]"
            )
            logger.info(f"HEDGE_BUY signal generated: Buy {target_symbol} - {reason}")
        else:
            signal_type = SignalType.SHORT
            target_symbol = self.symbol
            reason = (
                f"SHORT: {filters_passed[0]}, "
                f"Price ${bar['close']:.2f} > SMA, Filters: [{filter_str}]"
            )
            logger.info(f"SHORT signal generated: {reason}")

        return Signal(
            timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
            signal_type=signal_type,
            symbol=target_symbol,
            price=bar["close"],
            rsi=bar["rsi"],
            reason=reason,
            strength=strength,
            vwap=bar.get("vwap"),
            sma=bar.get(f"sma_{self.sma_filter.period}"),
            day_high=bar.get("high"),
            day_low=bar.get("low"),
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
        """Check for short/hedge exit signal."""
        if len(df) < 2:
            return None

        bar = df.iloc[-1]
        timestamp = df.index[-1]

        signal_type = SignalType.HEDGE_SELL if (is_hedge or self.use_inverse_etf) else SignalType.COVER
        target_symbol = self.inverse_symbol if (is_hedge or self.use_inverse_etf) else self.symbol
        exit_label = "HEDGE_SELL" if (is_hedge or self.use_inverse_etf) else "COVER"

        def create_signal(reason: str, strength: float = 1.0) -> Signal:
            price = current_hedge_price if is_hedge and current_hedge_price else bar["close"]
            return Signal(
                timestamp=timestamp if isinstance(timestamp, datetime) else timestamp.to_pydatetime(),
                signal_type=signal_type,
                symbol=target_symbol,
                price=price,
                rsi=bar.get("rsi", 0),
                reason=reason,
                strength=strength,
                vwap=bar.get("vwap"),
                sma=bar.get(f"sma_{self.sma_filter.period}"),
                day_high=bar.get("high"),
                day_low=bar.get("low"),
            )

        # Check RSI target reached
        rsi_result = self.rsi_filter.check_short_exit(df, bar, entry_price)
        if rsi_result.passed:
            reason = f"{exit_label}: TQQQ {rsi_result.reason}"
            logger.info(f"{exit_label} signal (RSI target): {reason}")
            return create_signal(reason)

        # Check stop loss
        if is_hedge and hedge_entry_price > 0 and current_hedge_price is not None:
            loss_pct = (hedge_entry_price - current_hedge_price) / hedge_entry_price
            if loss_pct >= stop_loss_pct:
                reason = f"{exit_label}: Stop loss triggered: -{loss_pct*100:.1f}% on SQQQ (threshold: -{stop_loss_pct*100}%)"
                logger.info(f"{exit_label} signal (stop loss): {reason}")
                return create_signal(reason, strength=0.0)
        elif not is_hedge:
            loss_pct = (bar["close"] - entry_price) / entry_price
            if loss_pct >= stop_loss_pct:
                reason = f"{exit_label}: Stop loss triggered: +{loss_pct*100:.1f}% move against short (threshold: +{stop_loss_pct*100}%)"
                logger.info(f"{exit_label} signal (stop loss): {reason}")
                return create_signal(reason, strength=0.0)

        # Check momentum shift (for direct shorts)
        if not is_hedge:
            prev_low_result = self.prev_hl_filter.check_short_exit(df, bar, entry_price)
            if prev_low_result.passed:
                reason = f"{exit_label}: {prev_low_result.reason}"
                logger.info(f"{exit_label} signal (momentum shift): {reason}")
                return create_signal(reason)

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

        This is the main entry point that dispatches to specific signal generators.
        """
        # Ensure indicators are calculated
        if "rsi" not in df.columns:
            df = self.prepare_data(df)

        settings = get_settings()
        short_sl = short_stop_loss_pct or settings.strategy.short_stop_loss_pct

        if has_position and entry_price is not None:
            if position_side == "hedge":
                return self.generate_short_exit_signal(
                    df, entry_price, short_sl,
                    is_hedge=True,
                    hedge_entry_price=hedge_entry_price or 0.0,
                    current_hedge_price=current_hedge_price,
                )
            elif position_side == "short":
                return self.generate_short_exit_signal(df, entry_price, short_sl, is_hedge=False)
            else:
                return self.generate_exit_signal(df, entry_price, stop_loss_pct)
        else:
            # Try long entry first
            long_signal = self.generate_entry_signal(df, has_position)
            if long_signal:
                return long_signal

            # Try short/hedge entry
            if self.short_enabled:
                return self.generate_short_entry_signal(df, has_position)

            return None
