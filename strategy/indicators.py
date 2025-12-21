"""
Technical indicators for trading strategy.
"""
import numpy as np
import pandas as pd
from typing import Optional


def calculate_rsi(prices: pd.Series, period: int = 2) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).

    Args:
        prices: Price series (typically close prices)
        period: RSI lookback period (default 2 for short-term)

    Returns:
        RSI values as pandas Series
    """
    delta = prices.diff()

    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)

    # Use Wilder's smoothing (exponential moving average)
    avg_gain = gain.ewm(alpha=1/period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))

    # Handle division by zero
    rsi = rsi.replace([np.inf, -np.inf], np.nan)
    rsi = rsi.fillna(50)  # Neutral RSI when undefined

    return rsi


def calculate_sma(prices: pd.Series, period: int = 200) -> pd.Series:
    """
    Calculate Simple Moving Average (SMA).

    Args:
        prices: Price series
        period: SMA lookback period

    Returns:
        SMA values as pandas Series
    """
    return prices.rolling(window=period, min_periods=period).mean()


def calculate_ema(prices: pd.Series, period: int = 20) -> pd.Series:
    """
    Calculate Exponential Moving Average (EMA).

    Args:
        prices: Price series
        period: EMA lookback period

    Returns:
        EMA values as pandas Series
    """
    return prices.ewm(span=period, adjust=False).mean()


def calculate_atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """
    Calculate Average True Range (ATR).

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        period: ATR lookback period

    Returns:
        ATR values as pandas Series
    """
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = abs(high - prev_close)
    tr3 = abs(low - prev_close)

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.ewm(alpha=1/period, min_periods=period, adjust=False).mean()

    return atr


def calculate_bollinger_bands(
    prices: pd.Series,
    period: int = 20,
    std_dev: float = 2.0,
) -> tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculate Bollinger Bands.

    Args:
        prices: Price series
        period: Lookback period
        std_dev: Standard deviation multiplier

    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    middle = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()

    upper = middle + (std * std_dev)
    lower = middle - (std * std_dev)

    return upper, middle, lower


def add_all_indicators(
    df: pd.DataFrame,
    rsi_period: int = 2,
    sma_period: int = 200,
    atr_period: int = 14,
) -> pd.DataFrame:
    """
    Add all required indicators to DataFrame.

    Args:
        df: DataFrame with OHLCV data
        rsi_period: RSI period
        sma_period: SMA period for trend filter
        atr_period: ATR period

    Returns:
        DataFrame with added indicator columns
    """
    df = df.copy()

    # RSI
    df["rsi"] = calculate_rsi(df["close"], period=rsi_period)

    # SMA for trend filter (dynamic column name)
    sma_col = f"sma_{sma_period}"
    df[sma_col] = calculate_sma(df["close"], period=sma_period)

    # ATR for volatility measurement
    df["atr"] = calculate_atr(df["high"], df["low"], df["close"], period=atr_period)

    # Previous day's high (for exit signal)
    df["prev_high"] = df["high"].shift(1)

    # Above/below SMA
    df["above_sma"] = df["close"] > df[sma_col]

    return df
