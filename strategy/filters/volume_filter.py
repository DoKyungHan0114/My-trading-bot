"""
Volume-based signal filter.
"""
import pandas as pd

from strategy.filters.base import SignalFilter, FilterResult


class VolumeFilter(SignalFilter):
    """
    Volume filter.

    Requires volume to be above a certain ratio of average volume.
    This helps avoid low-liquidity trades.
    """

    def __init__(
        self,
        min_ratio: float = 1.0,
        avg_period: int = 20,
        enabled: bool = False,
    ):
        """
        Initialize Volume filter.

        Args:
            min_ratio: Minimum volume ratio vs average (1.0 = average)
            avg_period: Period for volume average calculation
            enabled: Whether filter is active
        """
        super().__init__(enabled)
        self.min_ratio = min_ratio
        self.avg_period = avg_period

    @property
    def name(self) -> str:
        return f"Volume({self.min_ratio}x)"

    def check_long_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        skip = self._check_enabled()
        if skip:
            return skip

        if "volume_ratio" not in bar or pd.isna(bar.get("volume_ratio")):
            return FilterResult.skip("Volume ratio not available")

        volume_ratio = bar["volume_ratio"]

        if volume_ratio >= self.min_ratio:
            return FilterResult.success(
                reason=f"Vol({volume_ratio:.1f}x)",
                value=volume_ratio,
            )
        return FilterResult.failure(
            reason=f"Volume ratio {volume_ratio:.1f}x < {self.min_ratio}x",
            value=volume_ratio,
        )

    def check_long_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        # Volume not used for exit signals
        return FilterResult.skip("not applicable for exit")

    def check_short_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        # Same logic as long entry - we want sufficient volume
        return self.check_long_entry(df, bar)

    def check_short_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        # Volume not used for exit signals
        return FilterResult.skip("not applicable for exit")

    def get_volume_strength(self, bar: pd.Series) -> float:
        """
        Get volume strength indicator.

        Returns:
            1.0 = average volume, 2.0 = 2x average, etc.
        """
        if "volume_ratio" not in bar or pd.isna(bar.get("volume_ratio")):
            return 1.0
        return bar["volume_ratio"]
