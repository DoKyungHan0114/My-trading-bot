"""
Base filter interface and result types.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class FilterResult:
    """Result of a filter check."""
    passed: bool
    reason: str = ""
    value: Optional[float] = None
    threshold: Optional[float] = None

    def __bool__(self) -> bool:
        return self.passed

    @classmethod
    def success(cls, reason: str = "", value: Optional[float] = None) -> "FilterResult":
        """Create a passing filter result."""
        return cls(passed=True, reason=reason, value=value)

    @classmethod
    def failure(cls, reason: str = "", value: Optional[float] = None) -> "FilterResult":
        """Create a failing filter result."""
        return cls(passed=False, reason=reason, value=value)

    @classmethod
    def skip(cls, reason: str = "disabled") -> "FilterResult":
        """Create a skipped (passing) filter result."""
        return cls(passed=True, reason=f"[skipped: {reason}]")


class SignalFilter(ABC):
    """
    Abstract base class for signal filters.

    Each filter implements a specific technical indicator check.
    Filters can be enabled/disabled and configured independently.
    """

    def __init__(self, enabled: bool = True):
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    @abstractmethod
    def name(self) -> str:
        """Filter name for logging and display."""
        pass

    @abstractmethod
    def check_long_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        """
        Check if conditions are met for long entry.

        Args:
            df: Full DataFrame with indicators
            bar: Current bar data

        Returns:
            FilterResult indicating pass/fail
        """
        pass

    @abstractmethod
    def check_long_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        """
        Check if conditions are met for long exit.

        Args:
            df: Full DataFrame with indicators
            bar: Current bar data
            entry_price: Position entry price

        Returns:
            FilterResult indicating pass/fail
        """
        pass

    @abstractmethod
    def check_short_entry(self, df: pd.DataFrame, bar: pd.Series) -> FilterResult:
        """
        Check if conditions are met for short/hedge entry.

        Args:
            df: Full DataFrame with indicators
            bar: Current bar data

        Returns:
            FilterResult indicating pass/fail
        """
        pass

    @abstractmethod
    def check_short_exit(
        self,
        df: pd.DataFrame,
        bar: pd.Series,
        entry_price: float,
    ) -> FilterResult:
        """
        Check if conditions are met for short/hedge exit.

        Args:
            df: Full DataFrame with indicators
            bar: Current bar data
            entry_price: Position entry price

        Returns:
            FilterResult indicating pass/fail
        """
        pass

    def _check_enabled(self) -> Optional[FilterResult]:
        """Return skip result if filter is disabled."""
        if not self._enabled:
            return FilterResult.skip("disabled")
        return None
