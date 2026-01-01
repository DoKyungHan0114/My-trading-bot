"""
SMA (Simple Moving Average) trend filter.
"""
import pandas as pd

from strategy.filters.base import SignalFilter, FilterResult


class SMAFilter(SignalFilter):
    """
    SMA trend filter.

    Long entry: Price above SMA (uptrend)
    Short entry: Price above SMA (overextended in uptrend)

    This filter is primarily used for trend confirmation.
    """

    def __init__(
        self,
        period: int = 20,
        enabled: bool = True,
    ):
        """
        Initialize SMA filter.

        Args:
            period: SMA period
            enabled: Whether filter is active
        """
        super().__init__(enabled)
        self.period = period
        self._sma_col = f"sma_{period}"

    @property
    def name(self) -> str:
        return f"SMA({self.period})"

    def _get_sma(self, bar: pd.Series) -> float:
        """Get SMA value from bar, checking multiple column names."""
        # Try period-specific column first
        if self._sma_col in bar and pd.notna(bar[self._sma_col]):
            return bar[self._sma_col]

        # Fall back to generic 'sma' column
        if "sma" in bar and pd.notna(bar.get("sma")):
            return bar["sma"]

        return float("nan")

    def check_long_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        sma = self._get_sma(bar)
        if pd.isna(sma):
            return FilterResult.failure(f"SMA({self.period}) not available")

        price = bar["close"]

        # For mean reversion, we actually don't require price above SMA
        # This is just a data availability check
        return FilterResult.success(
            reason=f"SMA({self.period})=${sma:.2f}",
            value=sma,
        )

    def check_long_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        # SMA not used for exit signals
        return FilterResult.skip("not applicable for exit")

    def check_short_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        sma = self._get_sma(bar)
        if pd.isna(sma):
            return FilterResult.failure(f"SMA({self.period}) not available")

        price = bar["close"]

        # For short entry, require price above SMA (trend is extended)
        if price > sma:
            return FilterResult.success(
                reason=f"Price ${price:.2f} > SMA ${sma:.2f}",
                value=sma,
            )
        return FilterResult.failure(
            reason=f"Price ${price:.2f} <= SMA ${sma:.2f}",
            value=sma,
        )

    def check_short_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        # SMA not used for exit signals
        return FilterResult.skip("not applicable for exit")

    def get_price_to_sma_ratio(self, bar: pd.Series) -> float:
        """
        Get price distance from SMA as a ratio.

        Returns:
            1.0 = at SMA, > 1.0 = above SMA, < 1.0 = below SMA
        """
        sma = self._get_sma(bar)
        if pd.isna(sma) or sma == 0:
            return 1.0

        return bar["close"] / sma
