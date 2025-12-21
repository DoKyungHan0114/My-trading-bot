"""
Local data storage for caching and persistence.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from config.settings import DATA_DIR

logger = logging.getLogger(__name__)


class DataStorage:
    """Local file-based data storage."""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        Initialize storage.

        Args:
            cache_dir: Directory for cached data
        """
        self.cache_dir = cache_dir or DATA_DIR
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, symbol: str, timeframe: str, start: str, end: str) -> Path:
        """Generate cache file path."""
        filename = f"{symbol}_{timeframe}_{start}_{end}.parquet"
        return self.cache_dir / filename

    def save_bars(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> Path:
        """
        Save OHLCV data to parquet file.

        Args:
            df: DataFrame with OHLCV data
            symbol: Stock symbol
            timeframe: Data timeframe (daily, minute)
            start_date: Start date
            end_date: End date

        Returns:
            Path to saved file
        """
        path = self._get_cache_path(symbol, timeframe, start_date, end_date)
        df.to_parquet(path)
        logger.info(f"Saved {len(df)} bars to {path}")
        return path

    def load_bars(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> Optional[pd.DataFrame]:
        """
        Load OHLCV data from cache.

        Args:
            symbol: Stock symbol
            timeframe: Data timeframe
            start_date: Start date
            end_date: End date

        Returns:
            DataFrame if cached, None otherwise
        """
        path = self._get_cache_path(symbol, timeframe, start_date, end_date)

        if path.exists():
            df = pd.read_parquet(path)
            logger.info(f"Loaded {len(df)} bars from cache: {path}")
            return df

        return None

    def cache_exists(
        self,
        symbol: str,
        timeframe: str,
        start_date: str,
        end_date: str,
    ) -> bool:
        """Check if cached data exists."""
        path = self._get_cache_path(symbol, timeframe, start_date, end_date)
        return path.exists()

    def clear_cache(self, symbol: Optional[str] = None) -> int:
        """
        Clear cached data.

        Args:
            symbol: If provided, only clear data for this symbol

        Returns:
            Number of files deleted
        """
        count = 0
        pattern = f"{symbol}_*.parquet" if symbol else "*.parquet"

        for file in self.cache_dir.glob(pattern):
            file.unlink()
            count += 1

        logger.info(f"Cleared {count} cached files")
        return count

    def save_json(self, data: dict, filename: str) -> Path:
        """Save arbitrary JSON data."""
        path = self.cache_dir / filename
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return path

    def load_json(self, filename: str) -> Optional[dict]:
        """Load JSON data."""
        path = self.cache_dir / filename
        if path.exists():
            with open(path, "r") as f:
                return json.load(f)
        return None
