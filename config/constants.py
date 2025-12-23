"""
Trading system constants.
"""
from enum import Enum
from typing import Final


class TradingMode(Enum):
    """Trading execution modes."""
    BACKTEST = "backtest"
    PAPER = "paper"
    LIVE = "live"


class OrderSide(Enum):
    """Order side."""
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    """Order type."""
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderStatus(Enum):
    """Order status."""
    PENDING = "PENDING"
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class SignalType(Enum):
    """Trading signal types."""
    BUY = "BUY"              # Long entry (TQQQ)
    SELL = "SELL"            # Long exit (TQQQ)
    SHORT = "SHORT"          # Short entry (TQQQ direct short)
    COVER = "COVER"          # Short exit (buy to cover)
    HEDGE_BUY = "HEDGE_BUY"  # Hedge entry (SQQQ long)
    HEDGE_SELL = "HEDGE_SELL"  # Hedge exit (SQQQ sell)
    HOLD = "HOLD"


# Symbol
SYMBOL: Final[str] = "TQQQ"
STRATEGY_NAME: Final[str] = "RSI2_TQQQ"

# RSI Strategy Parameters
RSI_PERIOD: Final[int] = 2
RSI_OVERSOLD: Final[float] = 30.0  # 10 -> 25 -> 30 (더 자주 매수 신호)
RSI_OVERBOUGHT: Final[float] = 75.0  # 70 -> 75 (조금 더 오래 보유)
SMA_PERIOD: Final[int] = 20  # 200 -> 50 -> 20 (더 빠른 트렌드 필터)

# Risk Management
STOP_LOSS_PCT: Final[float] = 0.05  # 5%
CASH_RESERVE_PCT: Final[float] = 0.10  # 10% cash reserve
POSITION_SIZE_PCT: Final[float] = 0.90  # 90% of account

# VWAP Filter
VWAP_FILTER_ENABLED: Final[bool] = True  # VWAP 필터 사용
VWAP_ENTRY_BELOW: Final[bool] = True  # VWAP 아래에서만 매수

# ATR Dynamic Stop Loss
ATR_STOP_ENABLED: Final[bool] = False  # ATR 기반 손절 (기본 비활성)
ATR_STOP_MULTIPLIER: Final[float] = 2.0  # 손절 = 진입가 - (ATR * multiplier)
ATR_PERIOD: Final[int] = 14  # ATR 계산 기간

# Bollinger Bands Filter
BB_FILTER_ENABLED: Final[bool] = False  # 볼린저밴드 필터 (기본 비활성)
BB_PERIOD: Final[int] = 20
BB_STD_DEV: Final[float] = 2.0

# Volume Filter
VOLUME_FILTER_ENABLED: Final[bool] = False  # 거래량 필터 (기본 비활성)
VOLUME_MIN_RATIO: Final[float] = 1.0  # 20일 평균 대비 최소 비율
VOLUME_AVG_PERIOD: Final[int] = 20

# Inverse/Hedge Trading (SQQQ 롱으로 헷지)
SHORT_ENABLED: Final[bool] = True  # 헷지 전략 활성화
INVERSE_SYMBOL: Final[str] = "SQQQ"  # 인버스 ETF (TQQQ 숏 대신 SQQQ 롱)
USE_INVERSE_ETF: Final[bool] = True  # True: SQQQ 롱, False: TQQQ 직접 숏
RSI_OVERBOUGHT_SHORT: Final[float] = 90.0  # 헷지 진입 RSI 임계값 (매우 보수적)
RSI_OVERSOLD_SHORT: Final[float] = 60.0  # 헷지 청산 RSI 임계값 (빠른 청산)
SHORT_STOP_LOSS_PCT: Final[float] = 0.05  # 헷지 손절 5% (여유있게)
SHORT_POSITION_SIZE_PCT: Final[float] = 0.30  # 헷지 포지션 크기 30% (보수적)

# Time Constants
US_MARKET_OPEN_HOUR: Final[int] = 9
US_MARKET_OPEN_MINUTE: Final[int] = 30
US_MARKET_CLOSE_HOUR: Final[int] = 16
US_MARKET_CLOSE_MINUTE: Final[int] = 0
US_MARKET_TIMEZONE: Final[str] = "America/New_York"
AEST_TIMEZONE: Final[str] = "Australia/Sydney"

# ATO Fiscal Year
ATO_FY_START_MONTH: Final[int] = 7  # July
ATO_FY_START_DAY: Final[int] = 1
ATO_LONG_TERM_DAYS: Final[int] = 365  # 12 months for CGT discount

# API Rate Limits (Alpaca Free Tier)
API_CALLS_PER_MINUTE: Final[int] = 200
WEBSOCKET_CONNECTIONS_MAX: Final[int] = 1

# Logging
LOG_DATE_FORMAT: Final[str] = "%Y-%m-%d %H:%M:%S"
TRADE_LOG_FILENAME: Final[str] = "trades.json"
SYSTEM_LOG_FILENAME: Final[str] = "system.log"
ERROR_LOG_FILENAME: Final[str] = "error.log"

# Backtest Defaults (Weekly focus)
BACKTEST_DAYS: Final[int] = 7  # 일주일 단위
INITIAL_CAPITAL: Final[float] = 10000.0

# Exchange Rate API (for AUD conversion)
EXCHANGE_RATE_API_URL: Final[str] = "https://api.exchangerate-api.com/v4/latest/USD"

# Discord Message Limits
DISCORD_MAX_MESSAGE_LENGTH: Final[int] = 2000
