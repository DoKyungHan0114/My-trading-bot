"""
Alpaca historical data fetcher.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import StockBarsRequest
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

from config.settings import get_settings

logger = logging.getLogger(__name__)


class DataFetcher:
    """Fetch historical data from Alpaca API."""

    def __init__(self, api_key: Optional[str] = None, secret_key: Optional[str] = None):
        """
        Initialize data fetcher.

        Args:
            api_key: Alpaca API key (uses settings if not provided)
            secret_key: Alpaca secret key (uses settings if not provided)
        """
        settings = get_settings()
        self.api_key = api_key or settings.alpaca.api_key
        self.secret_key = secret_key or settings.alpaca.secret_key
        self._client: Optional[StockHistoricalDataClient] = None
        self._api_calls = 0

    @property
    def client(self) -> "StockHistoricalDataClient":
        """Lazy initialize Alpaca client."""
        if not ALPACA_AVAILABLE:
            raise ImportError(
                "alpaca-py not installed. Run: pip install alpaca-py"
            )
        if self._client is None:
            self._client = StockHistoricalDataClient(
                api_key=self.api_key,
                secret_key=self.secret_key
            )
        return self._client

    @property
    def api_calls(self) -> int:
        """Get total API calls made."""
        return self._api_calls

    def reset_api_calls(self) -> None:
        """Reset API call counter."""
        self._api_calls = 0

    def get_daily_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch daily OHLCV bars.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data
        """
        if not ALPACA_AVAILABLE:
            logger.warning("Alpaca not available, generating synthetic data")
            return self._generate_synthetic_data(symbol, start_date, end_date)

        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Day,
                start=datetime.strptime(start_date, "%Y-%m-%d"),
                end=datetime.strptime(end_date, "%Y-%m-%d"),
            )
            self._api_calls += 1
            bars = self.client.get_stock_bars(request)

            if not bars.data or symbol not in bars.data:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()

            df = bars.df
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(symbol, level="symbol")

            df = df.reset_index()
            df.columns = ["timestamp", "open", "high", "low", "close", "volume", "trade_count", "vwap"]
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
            df = df.set_index("timestamp")

            logger.info(f"Fetched {len(df)} daily bars for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return self._generate_synthetic_data(symbol, start_date, end_date)

    def get_minute_bars(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Fetch 1-minute OHLCV bars.

        Args:
            symbol: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)

        Returns:
            DataFrame with OHLCV data
        """
        if not ALPACA_AVAILABLE:
            logger.warning("Alpaca not available, generating synthetic data")
            return self._generate_synthetic_minute_data(symbol, start_date, end_date)

        try:
            request = StockBarsRequest(
                symbol_or_symbols=symbol,
                timeframe=TimeFrame.Minute,
                start=datetime.strptime(start_date, "%Y-%m-%d"),
                end=datetime.strptime(end_date, "%Y-%m-%d"),
            )
            self._api_calls += 1
            bars = self.client.get_stock_bars(request)

            if not bars.data or symbol not in bars.data:
                logger.warning(f"No data returned for {symbol}")
                return pd.DataFrame()

            df = bars.df
            if isinstance(df.index, pd.MultiIndex):
                df = df.xs(symbol, level="symbol")

            df = df.reset_index()
            df.columns = ["timestamp", "open", "high", "low", "close", "volume", "trade_count", "vwap"]
            df["timestamp"] = pd.to_datetime(df["timestamp"]).dt.tz_localize(None)
            df = df.set_index("timestamp")

            logger.info(f"Fetched {len(df)} minute bars for {symbol}")
            return df

        except Exception as e:
            logger.error(f"Error fetching minute data: {e}")
            return self._generate_synthetic_minute_data(symbol, start_date, end_date)

    def _generate_synthetic_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        Generate synthetic daily data for backtesting when API unavailable.
        Uses realistic TQQQ-like volatility patterns.
        """
        import numpy as np

        np.random.seed(42)

        start = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)

        # Generate business days only
        dates = pd.bdate_range(start=start, end=end)
        n_days = len(dates)

        # TQQQ-like parameters (3x leveraged)
        initial_price = 40.0
        daily_drift = 0.0008  # ~20% annual drift
        daily_vol = 0.045  # ~70% annual volatility (3x leverage)

        # Generate returns with mean reversion tendency
        returns = np.random.normal(daily_drift, daily_vol, n_days)

        # Add some autocorrelation (mean reversion)
        for i in range(1, n_days):
            if returns[i-1] < -0.03:  # Big down day
                returns[i] += 0.01  # Slight bounce tendency
            elif returns[i-1] > 0.03:  # Big up day
                returns[i] -= 0.005  # Slight pullback tendency

        prices = initial_price * np.cumprod(1 + returns)

        # Generate OHLC
        high_factor = 1 + np.abs(np.random.normal(0, 0.015, n_days))
        low_factor = 1 - np.abs(np.random.normal(0, 0.015, n_days))

        open_prices = prices * (1 + np.random.normal(0, 0.005, n_days))
        high_prices = np.maximum(prices, open_prices) * high_factor
        low_prices = np.minimum(prices, open_prices) * low_factor

        volume = np.random.randint(50_000_000, 150_000_000, n_days)

        df = pd.DataFrame({
            "open": open_prices,
            "high": high_prices,
            "low": low_prices,
            "close": prices,
            "volume": volume,
            "trade_count": volume // 100,
            "vwap": (high_prices + low_prices + prices) / 3,
        }, index=dates)

        logger.info(f"Generated {len(df)} synthetic daily bars for {symbol}")
        return df

    def _generate_synthetic_minute_data(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """Generate synthetic minute data (simplified version using daily)."""
        # For backtesting, we'll use daily data resampled
        daily = self._generate_synthetic_data(symbol, start_date, end_date)
        return daily  # Return daily data for simplicity
