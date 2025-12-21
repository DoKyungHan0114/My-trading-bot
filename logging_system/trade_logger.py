"""
Trade logging system for ATO tax compliance.
"""
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import pytz
import requests

from config.constants import AEST_TIMEZONE, EXCHANGE_RATE_API_URL, STRATEGY_NAME
from config.settings import LOGS_DIR

logger = logging.getLogger(__name__)


class ExchangeRateService:
    """Service to fetch USD/AUD exchange rates."""

    def __init__(self):
        self._cache: dict[str, float] = {}
        self._cache_date: Optional[str] = None

    def get_rate(self, date: Optional[datetime] = None) -> float:
        """
        Get USD to AUD exchange rate.

        Args:
            date: Date for rate (uses current if None)

        Returns:
            USD to AUD exchange rate
        """
        date_str = (date or datetime.utcnow()).strftime("%Y-%m-%d")

        # Check cache
        if date_str in self._cache:
            return self._cache[date_str]

        try:
            response = requests.get(EXCHANGE_RATE_API_URL, timeout=5)
            response.raise_for_status()
            data = response.json()
            rate = data["rates"].get("AUD", 1.55)  # Default fallback
            self._cache[date_str] = rate
            return rate
        except Exception as e:
            logger.warning(f"Failed to fetch exchange rate: {e}")
            return 1.55  # Approximate fallback rate


class TradeLog:
    """Single trade log entry."""

    def __init__(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fill_price: float,
        order_type: str,
        commission: float = 0.0,
        fees: float = 0.0,
        signal_reason: str = "",
        order_id_alpaca: str = "",
        realized_pnl_usd: Optional[float] = None,
        holding_period_days: Optional[int] = None,
        exchange_rate: Optional[float] = None,
    ):
        self.trade_id = str(uuid.uuid4())
        self.timestamp_utc = datetime.utcnow()
        self.symbol = symbol
        self.side = side
        self.quantity = quantity
        self.price = price
        self.fill_price = fill_price
        self.order_type = order_type
        self.commission = commission
        self.fees = fees
        self.signal_reason = signal_reason
        self.order_id_alpaca = order_id_alpaca
        self.realized_pnl_usd = realized_pnl_usd
        self.holding_period_days = holding_period_days

        # Exchange rate
        self.exchange_rate = exchange_rate or ExchangeRateService().get_rate(self.timestamp_utc)

        # Calculate values
        self.total_value_usd = quantity * fill_price
        self.total_value_aud = self.total_value_usd * self.exchange_rate
        self.slippage = (
            (fill_price - price) / price if price > 0 else 0
        )
        self.realized_pnl_aud = (
            realized_pnl_usd * self.exchange_rate if realized_pnl_usd else None
        )

    @property
    def timestamp_aest(self) -> datetime:
        """Get timestamp in AEST/AEDT timezone."""
        utc_tz = pytz.UTC
        aest_tz = pytz.timezone(AEST_TIMEZONE)
        utc_time = utc_tz.localize(self.timestamp_utc)
        return utc_time.astimezone(aest_tz)

    def to_dict(self) -> dict:
        """Convert to dictionary matching required schema."""
        return {
            "trade_id": self.trade_id,
            "timestamp_utc": self.timestamp_utc.isoformat(),
            "timestamp_aest": self.timestamp_aest.isoformat(),
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "total_value_usd": self.total_value_usd,
            "total_value_aud": self.total_value_aud,
            "exchange_rate": self.exchange_rate,
            "commission": self.commission,
            "fees": self.fees,
            "order_type": self.order_type,
            "fill_price": self.fill_price,
            "slippage": self.slippage,
            "realized_pnl_usd": self.realized_pnl_usd,
            "realized_pnl_aud": self.realized_pnl_aud,
            "holding_period_days": self.holding_period_days,
            "strategy": STRATEGY_NAME,
            "signal_reason": self.signal_reason,
            "order_id_alpaca": self.order_id_alpaca,
        }


class TradeLogger:
    """Logger for all trades with JSON persistence."""

    def __init__(self, log_dir: Optional[Path] = None):
        """
        Initialize trade logger.

        Args:
            log_dir: Directory for log files
        """
        self.log_dir = log_dir or LOGS_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / "trades.json"
        self.exchange_service = ExchangeRateService()
        self._trades: list[dict] = []
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing trades from file."""
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    self._trades = json.load(f)
                logger.info(f"Loaded {len(self._trades)} existing trades")
            except Exception as e:
                logger.warning(f"Failed to load existing trades: {e}")
                self._trades = []

    def _save(self) -> None:
        """Save trades to file."""
        try:
            with open(self.log_file, "w") as f:
                json.dump(self._trades, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save trades: {e}")

    def log_trade(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        fill_price: float,
        order_type: str = "MARKET",
        commission: float = 0.0,
        fees: float = 0.0,
        signal_reason: str = "",
        order_id_alpaca: str = "",
        realized_pnl_usd: Optional[float] = None,
        holding_period_days: Optional[int] = None,
    ) -> TradeLog:
        """
        Log a trade.

        Returns:
            TradeLog entry
        """
        trade = TradeLog(
            symbol=symbol,
            side=side,
            quantity=quantity,
            price=price,
            fill_price=fill_price,
            order_type=order_type,
            commission=commission,
            fees=fees,
            signal_reason=signal_reason,
            order_id_alpaca=order_id_alpaca,
            realized_pnl_usd=realized_pnl_usd,
            holding_period_days=holding_period_days,
        )

        self._trades.append(trade.to_dict())
        self._save()

        logger.info(
            f"Logged trade: {side} {quantity:.4f} {symbol} @ ${fill_price:.2f} "
            f"(AUD ${trade.total_value_aud:.2f})"
        )

        return trade

    def get_trades(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        symbol: Optional[str] = None,
    ) -> list[dict]:
        """
        Get trades with optional filters.

        Args:
            start_date: Filter from this date
            end_date: Filter to this date
            symbol: Filter by symbol

        Returns:
            List of matching trades
        """
        trades = self._trades

        if symbol:
            trades = [t for t in trades if t["symbol"] == symbol]

        if start_date:
            start_str = start_date.isoformat()
            trades = [t for t in trades if t["timestamp_utc"] >= start_str]

        if end_date:
            end_str = end_date.isoformat()
            trades = [t for t in trades if t["timestamp_utc"] <= end_str]

        return trades

    def get_trade_count(self) -> int:
        """Get total number of logged trades."""
        return len(self._trades)

    def clear(self) -> None:
        """Clear all trades (use with caution)."""
        self._trades = []
        self._save()
        logger.warning("All trades cleared")
