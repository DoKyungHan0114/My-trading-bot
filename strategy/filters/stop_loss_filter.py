"""
Stop Loss filter for exit signals.
"""
import pandas as pd

from strategy.filters.base import SignalFilter, FilterResult


class StopLossFilter(SignalFilter):
    """
    Stop Loss filter.

    Checks if price has moved against position beyond threshold.
    Supports both fixed percentage and ATR-based stop loss.
    """

    def __init__(
        self,
        stop_loss_pct: float = 0.05,
        atr_multiplier: float = 2.0,
        use_atr: bool = False,
        enabled: bool = True,
    ):
        """
        Initialize Stop Loss filter.

        Args:
            stop_loss_pct: Fixed stop loss percentage (e.g., 0.05 = 5%)
            atr_multiplier: ATR multiplier for dynamic stop loss
            use_atr: Use ATR-based stop loss instead of fixed
            enabled: Whether filter is active
        """
        super().__init__(enabled)
        self.stop_loss_pct = stop_loss_pct
        self.atr_multiplier = atr_multiplier
        self.use_atr = use_atr

    @property
    def name(self) -> str:
        if self.use_atr:
            return f"StopLoss(ATR×{self.atr_multiplier})"
        return f"StopLoss({self.stop_loss_pct:.1%})"

    def check_long_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        # Stop loss not used for entry
        return FilterResult.skip("not applicable for entry")

    def check_long_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        current_price = bar["close"]
        stop_price = self._calculate_stop_price(bar, entry_price, is_long=True)

        loss_pct = (current_price - entry_price) / entry_price

        if current_price <= stop_price:
            return FilterResult.success(
                reason=f"Stop loss triggered: {loss_pct*100:.1f}% loss (threshold: -{self.stop_loss_pct*100:.0f}%)",
                value=loss_pct,
            )
        return FilterResult.failure(
            reason=f"No stop loss: {loss_pct*100:+.1f}%",
            value=loss_pct,
        )

    def check_short_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        # Stop loss not used for entry
        return FilterResult.skip("not applicable for entry")

    def check_short_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        current_price = bar["close"]
        stop_price = self._calculate_stop_price(bar, entry_price, is_long=False)

        # For shorts, loss occurs when price rises
        loss_pct = (current_price - entry_price) / entry_price

        if current_price >= stop_price:
            return FilterResult.success(
                reason=f"Stop loss triggered: +{loss_pct*100:.1f}% move against short (threshold: +{self.stop_loss_pct*100:.0f}%)",
                value=loss_pct,
            )
        return FilterResult.failure(
            reason=f"No stop loss: {loss_pct*100:+.1f}%",
            value=loss_pct,
        )

    def _calculate_stop_price(
        self,
        bar: pd.Series,
        entry_price: float,
        is_long: bool,
    ) -> float:
        """
        Calculate stop price based on configuration.

        Args:
            bar: Current bar with ATR if using dynamic stop
            entry_price: Position entry price
            is_long: True for long positions

        Returns:
            Stop price
        """
        if self.use_atr and "atr" in bar and pd.notna(bar.get("atr")):
            atr = bar["atr"]
            stop_distance = atr * self.atr_multiplier

            if is_long:
                return entry_price - stop_distance
            else:
                return entry_price + stop_distance
        else:
            # Fixed percentage stop
            if is_long:
                return entry_price * (1 - self.stop_loss_pct)
            else:
                return entry_price * (1 + self.stop_loss_pct)

    def get_current_risk(
        self,
        bar: pd.Series,
        entry_price: float,
        is_long: bool = True,
    ) -> float:
        """
        Get current risk as percentage of entry price.

        Returns:
            Negative = loss, Positive = profit
        """
        current_price = bar["close"]

        if is_long:
            return (current_price - entry_price) / entry_price
        else:
            return (entry_price - current_price) / entry_price


class PreviousHighLowFilter(SignalFilter):
    """
    Previous day high/low breakout filter.

    Long exit: Close above previous high
    Short exit: Close below previous low
    """

    def __init__(self, enabled: bool = True):
        super().__init__(enabled)

    @property
    def name(self) -> str:
        return "PrevHighLow"

    def check_long_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        return FilterResult.skip("not applicable for entry")

    def check_long_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "prev_high" not in bar or pd.isna(bar.get("prev_high")):
            return FilterResult.skip("Previous high not available")

        price = bar["close"]
        prev_high = bar["prev_high"]

        if price > prev_high:
            return FilterResult.success(
                reason=f"Close ${price:.2f} > Previous High ${prev_high:.2f}",
                value=prev_high,
            )
        return FilterResult.failure(
            reason=f"Close ${price:.2f} <= Previous High ${prev_high:.2f}",
            value=prev_high,
        )

    def check_short_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        return FilterResult.skip("not applicable for entry")

    def check_short_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "prev_low" not in bar or pd.isna(bar.get("prev_low")):
            return FilterResult.skip("Previous low not available")

        price = bar["close"]
        prev_low = bar["prev_low"]

        if price < prev_low:
            return FilterResult.success(
                reason=f"Close ${price:.2f} < Previous Low ${prev_low:.2f}",
                value=prev_low,
            )
        return FilterResult.failure(
            reason=f"Close ${price:.2f} >= Previous Low ${prev_low:.2f}",
            value=prev_low,
        )
