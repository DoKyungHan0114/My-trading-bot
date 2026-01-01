"""
VWAP-based signal filter.
"""
import pandas as pd

from strategy.filters.base import SignalFilter, FilterResult


class VWAPFilter(SignalFilter):
    """
    VWAP (Volume Weighted Average Price) filter.

    Long entry: Price below VWAP (buying at discount)
    Short entry: Price above VWAP (selling at premium)
    """

    def __init__(
        self,
        entry_below: bool = True,
        enabled: bool = False,
    ):
        """
        Initialize VWAP filter.

        Args:
            entry_below: If True, require price below VWAP for long entry
            enabled: Whether filter is active
        """
        super().__init__(enabled)
        self.entry_below = entry_below

    @property
    def name(self) -> str:
        direction = "below" if self.entry_below else "above"
        return f"VWAP({direction})"

    def check_long_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "vwap" not in bar or pd.isna(bar.get("vwap")):
            return FilterResult.skip("VWAP not available")

        price = bar["close"]
        vwap = bar["vwap"]

        if self.entry_below:
            if price < vwap:
                return FilterResult.success(
                    reason=f"VWAP(below ${vwap:.2f})",
                    value=vwap,
                )
            return FilterResult.failure(
                reason=f"Price ${price:.2f} >= VWAP ${vwap:.2f}",
                value=vwap,
            )
        else:
            if price > vwap:
                return FilterResult.success(
                    reason=f"VWAP(above ${vwap:.2f})",
                    value=vwap,
                )
            return FilterResult.failure(
                reason=f"Price ${price:.2f} <= VWAP ${vwap:.2f}",
                value=vwap,
            )

    def check_long_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        # VWAP is not used for exit signals
        return FilterResult.skip("not applicable for exit")

    def check_short_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "vwap" not in bar or pd.isna(bar.get("vwap")):
            return FilterResult.skip("VWAP not available")

        price = bar["close"]
        vwap = bar["vwap"]

        # For short entry, we want price ABOVE VWAP (overextended)
        if price > vwap:
            return FilterResult.success(
                reason=f"VWAP(above ${vwap:.2f})",
                value=vwap,
            )
        return FilterResult.failure(
            reason=f"Price ${price:.2f} <= VWAP ${vwap:.2f}",
            value=vwap,
        )

    def check_short_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        # VWAP is not used for exit signals
        return FilterResult.skip("not applicable for exit")
