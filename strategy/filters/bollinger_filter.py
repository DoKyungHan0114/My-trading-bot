"""
Bollinger Bands signal filter.
"""
import pandas as pd

from strategy.filters.base import SignalFilter, FilterResult


class BollingerBandsFilter(SignalFilter):
    """
    Bollinger Bands filter.

    Long entry: Price at or below lower band
    Short entry: Price at or above upper band
    """

    def __init__(
        self,
        period: int = 20,
        std_dev: float = 2.0,
        enabled: bool = False,
    ):
        """
        Initialize Bollinger Bands filter.

        Args:
            period: Period for moving average
            std_dev: Number of standard deviations
            enabled: Whether filter is active
        """
        super().__init__(enabled)
        self.period = period
        self.std_dev = std_dev

    @property
    def name(self) -> str:
        return f"BB({self.period}, {self.std_dev})"

    def check_long_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "bb_lower" not in bar or pd.isna(bar.get("bb_lower")):
            return FilterResult.skip("BB lower band not available")

        price = bar["close"]
        bb_lower = bar["bb_lower"]

        if price <= bb_lower:
            return FilterResult.success(
                reason=f"BB(lower ${bb_lower:.2f})",
                value=bb_lower,
            )
        return FilterResult.failure(
            reason=f"Price ${price:.2f} > BB lower ${bb_lower:.2f}",
            value=bb_lower,
        )

    def check_long_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        # Bollinger Bands not used for exit signals by default
        return FilterResult.skip("not applicable for exit")

    def check_short_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "bb_upper" not in bar or pd.isna(bar.get("bb_upper")):
            return FilterResult.skip("BB upper band not available")

        price = bar["close"]
        bb_upper = bar["bb_upper"]

        if price >= bb_upper:
            return FilterResult.success(
                reason=f"BB(upper ${bb_upper:.2f})",
                value=bb_upper,
            )
        return FilterResult.failure(
            reason=f"Price ${price:.2f} < BB upper ${bb_upper:.2f}",
            value=bb_upper,
        )

    def check_short_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        # Bollinger Bands not used for exit signals by default
        return FilterResult.skip("not applicable for exit")

    def get_band_position(self, bar: pd.Series) -> float:
        """
        Get current price position within Bollinger Bands.

        Returns:
            0.0 = at lower band, 0.5 = at middle, 1.0 = at upper band
            Values outside bands will be < 0 or > 1
        """
        if any(key not in bar for key in ["bb_lower", "bb_upper"]):
            return 0.5

        bb_lower = bar["bb_lower"]
        bb_upper = bar["bb_upper"]
        price = bar["close"]

        if pd.isna(bb_lower) or pd.isna(bb_upper):
            return 0.5

        band_width = bb_upper - bb_lower
        if band_width <= 0:
            return 0.5

        return (price - bb_lower) / band_width
