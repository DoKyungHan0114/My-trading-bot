"""
Configuration settings loaded from environment variables.
"""
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from config.constants import (
    ATR_PERIOD,
    ATR_STOP_ENABLED,
    ATR_STOP_MULTIPLIER,
    BACKTEST_DAYS,
    BB_FILTER_ENABLED,
    BB_PERIOD,
    BB_STD_DEV,
    CASH_RESERVE_PCT,
    INITIAL_CAPITAL,
    POSITION_SIZE_PCT,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    RSI_PERIOD,
    SMA_PERIOD,
    STOP_LOSS_PCT,
    SYMBOL,
    VOLUME_AVG_PERIOD,
    VOLUME_FILTER_ENABLED,
    VOLUME_MIN_RATIO,
    VWAP_ENTRY_BELOW,
    VWAP_FILTER_ENABLED,
    TradingMode,
)

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
REPORTS_DIR = PROJECT_ROOT / "reports"
DATA_DIR = PROJECT_ROOT / "data" / "cache"

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)
REPORTS_DIR.mkdir(exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class AlpacaConfig:
    """Alpaca API configuration."""
    api_key: str = field(default_factory=lambda: os.getenv("ALPACA_API_KEY", ""))
    secret_key: str = field(default_factory=lambda: os.getenv("ALPACA_SECRET_KEY", ""))
    base_url: str = field(
        default_factory=lambda: os.getenv(
            "ALPACA_BASE_URL", "https://paper-api.alpaca.markets"
        )
    )
    data_url: str = "https://data.alpaca.markets"

    @property
    def is_paper(self) -> bool:
        """Check if using paper trading."""
        return "paper" in self.base_url.lower()

    def validate(self) -> bool:
        """Validate API credentials are set."""
        return bool(self.api_key and self.secret_key)


@dataclass
class StrategyConfig:
    """RSI(2) strategy configuration with multi-indicator support."""
    # Core parameters
    symbol: str = SYMBOL
    rsi_period: int = RSI_PERIOD
    rsi_oversold: float = RSI_OVERSOLD
    rsi_overbought: float = RSI_OVERBOUGHT
    sma_period: int = SMA_PERIOD
    stop_loss_pct: float = STOP_LOSS_PCT
    position_size_pct: float = POSITION_SIZE_PCT
    cash_reserve_pct: float = CASH_RESERVE_PCT
    # VWAP Filter
    vwap_filter_enabled: bool = VWAP_FILTER_ENABLED
    vwap_entry_below: bool = VWAP_ENTRY_BELOW
    # ATR Dynamic Stop Loss
    atr_stop_enabled: bool = ATR_STOP_ENABLED
    atr_stop_multiplier: float = ATR_STOP_MULTIPLIER
    atr_period: int = ATR_PERIOD
    # Bollinger Bands Filter
    bb_filter_enabled: bool = BB_FILTER_ENABLED
    bb_period: int = BB_PERIOD
    bb_std_dev: float = BB_STD_DEV
    # Volume Filter
    volume_filter_enabled: bool = VOLUME_FILTER_ENABLED
    volume_min_ratio: float = VOLUME_MIN_RATIO
    volume_avg_period: int = VOLUME_AVG_PERIOD


@dataclass
class BacktestConfig:
    """Backtest configuration (weekly focus)."""
    days: int = BACKTEST_DAYS  # 7 days default
    initial_capital: float = INITIAL_CAPITAL
    commission: float = 0.0  # Alpaca has no commission
    slippage_pct: float = 0.001  # 0.1% slippage assumption

    @property
    def start_date(self) -> str:
        """Calculate start date (N days ago)."""
        return (datetime.now() - timedelta(days=self.days)).strftime("%Y-%m-%d")

    @property
    def end_date(self) -> str:
        """Calculate end date (today)."""
        return datetime.now().strftime("%Y-%m-%d")


@dataclass
class DiscordConfig:
    """Discord webhook configuration."""
    webhook_url: str = field(
        default_factory=lambda: os.getenv("DISCORD_WEBHOOK_URL", "")
    )
    daily_webhook_url: str = field(
        default_factory=lambda: os.getenv("DISCORD_DAILY_WEBHOOK_URL", "")
    )
    weekly_webhook_url: str = field(
        default_factory=lambda: os.getenv("DISCORD_WEEKLY_WEBHOOK_URL", "")
    )
    enabled: bool = field(
        default_factory=lambda: bool(os.getenv("DISCORD_WEBHOOK_URL", ""))
    )


@dataclass
class Settings:
    """Main settings container."""
    alpaca: AlpacaConfig = field(default_factory=AlpacaConfig)
    strategy: StrategyConfig = field(default_factory=StrategyConfig)
    backtest: BacktestConfig = field(default_factory=BacktestConfig)
    discord: DiscordConfig = field(default_factory=DiscordConfig)
    mode: TradingMode = TradingMode.BACKTEST

    def set_mode(self, mode: str) -> None:
        """Set trading mode from string."""
        self.mode = TradingMode(mode.lower())


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get global settings instance."""
    return settings


def configure_for_mode(mode: str) -> Settings:
    """Configure settings for a specific trading mode."""
    settings.set_mode(mode)
    return settings
