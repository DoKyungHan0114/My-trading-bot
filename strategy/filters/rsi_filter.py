"""
RSI-based signal filter.
"""
import pandas as pd

from strategy.filters.base import SignalFilter, FilterResult


class RSIFilter(SignalFilter):
    """
    RSI (Relative Strength Index) filter.

    Long entry: RSI <= oversold threshold
    Long exit: RSI >= overbought threshold
    Short entry: RSI >= overbought_short threshold
    Short exit: RSI <= oversold_short threshold
    """

    def __init__(
        self,
        period: int = 2,
        oversold: float = 30.0,
        overbought: float = 70.0,
        overbought_short: float = 90.0,
        oversold_short: float = 60.0,
        enabled: bool = True,
    ):
        super().__init__(enabled)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.overbought_short = overbought_short
        self.oversold_short = oversold_short

    @property
    def name(self) -> str:
        return f"RSI({self.period})"

    def check_long_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "rsi" not in bar or pd.isna(bar["rsi"]):
            return FilterResult.failure("RSI not available")

        rsi = bar["rsi"]
        if rsi <= self.oversold:
            return FilterResult.success(
                reason=f"RSI({self.period})={rsi:.1f} <= {self.oversold}",
                value=rsi,
            )

        return FilterResult.failure(
            reason=f"RSI({self.period})={rsi:.1f} > {self.oversold}",
            value=rsi,
        )

    def check_long_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "rsi" not in bar or pd.isna(bar["rsi"]):
            return FilterResult.failure("RSI not available")

        rsi = bar["rsi"]
        if rsi >= self.overbought:
            return FilterResult.success(
                reason=f"RSI({self.period})={rsi:.1f} >= {self.overbought}",
                value=rsi,
            )

        return FilterResult.failure(
            reason=f"RSI({self.period})={rsi:.1f} < {self.overbought}",
            value=rsi,
        )

    def check_short_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "rsi" not in bar or pd.isna(bar["rsi"]):
            return FilterResult.failure("RSI not available")

        rsi = bar["rsi"]
        if rsi >= self.overbought_short:
            return FilterResult.success(
                reason=f"RSI({self.period})={rsi:.1f} >= {self.overbought_short}",
                value=rsi,
            )

        return FilterResult.failure(
            reason=f"RSI({self.period})={rsi:.1f} < {self.overbought_short}",
            value=rsi,
        )

    def check_short_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "rsi" not in bar or pd.isna(bar["rsi"]):
            return FilterResult.failure("RSI not available")

        rsi = bar["rsi"]
        if rsi <= self.oversold_short:
            return FilterResult.success(
                reason=f"RSI({self.period})={rsi:.1f} <= {self.oversold_short}",
                value=rsi,
            )

        return FilterResult.failure(
            reason=f"RSI({self.period})={rsi:.1f} > {self.oversold_short}",
            value=rsi,
        )

    def calculate_strength(self, rsi: float, for_long: bool = True) -> float:
        """
        Calculate signal strength based on RSI value.

        Args:
            rsi: Current RSI value
            for_long: True for long signals, False for short

        Returns:
            Strength value between 0 and 1
        """
        if for_long:
            # More oversold = stronger signal
            if rsi >= self.oversold:
                return 0.0
            return min(1.0, (self.oversold - rsi) / self.oversold + 0.5)
        else:
            # More overbought = stronger signal
            if rsi <= self.overbought_short:
                return 0.0
            return min(1.0, (rsi - self.overbought_short) / (100 - self.overbought_short) + 0.5)
