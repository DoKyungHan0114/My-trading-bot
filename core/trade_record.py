"""
Unified TradeRecord class for consistent trade data across all modules.

This module consolidates trade recording logic that was previously duplicated across:
- logging_system/trade_logger.py (TradeLog)
- backtest/engine.py (BacktestTrade)
- main.py (ad-hoc trade logging)
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import pytz

from config.constants import AEST_TIMEZONE, STRATEGY_NAME


@dataclass
class TradeRecord:
    """
    Unified trade record representation.

    Used consistently across:
    - Live trading (main.py)
    - Backtesting (backtest/engine.py)
    - Trade logging (logging_system/trade_logger.py)
    """
    # Required fields
    symbol: str
    side: str  # BUY, SELL, SHORT, COVER, HEDGE_BUY, HEDGE_SELL
    quantity: float
    entry_price: float

    # Optional fields with defaults
    exit_price: Optional[float] = None
    entry_time: datetime = field(default_factory=datetime.utcnow)
    exit_time: Optional[datetime] = None
    trade_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Order details
    order_type: str = "MARKET"
    order_id_alpaca: str = ""
    signal_reason: str = ""
    exit_reason: str = ""

    # Costs
    commission: float = 0.0
    fees: float = 0.0
    slippage: float = 0.0

    # Indicator values at trade time
    rsi_value: Optional[float] = None
    vwap_value: Optional[float] = None
    sma_value: Optional[float] = None
    atr_value: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None

    # Exchange rate for AUD conversion
    exchange_rate: Optional[float] = None

    # Computed after exit
    _pnl: Optional[float] = field(default=None, repr=False)

    @property
    def is_closed(self) -> bool:
        """Check if trade has been closed."""
        return self.exit_price is not None and self.exit_time is not None

    @property
    def is_long(self) -> bool:
        """Check if this is a long trade."""
        return self.side in ("BUY", "HEDGE_BUY")

    @property
    def is_short(self) -> bool:
        """Check if this is a short trade."""
        return self.side in ("SHORT", "SELL")

    @property
    def is_hedge(self) -> bool:
        """Check if this is a hedge trade."""
        return self.side in ("HEDGE_BUY", "HEDGE_SELL")

    @property
    def pnl(self) -> float:
        """
        Calculate profit/loss in USD.

        Returns:
            PnL amount (positive = profit, negative = loss)
        """
        if self._pnl is not None:
            return self._pnl

        if not self.is_closed:
            return 0.0

        if self.side in ("BUY", "HEDGE_BUY"):
            # Long: profit when exit > entry
            gross_pnl = (self.exit_price - self.entry_price) * self.quantity
        elif self.side == "SHORT":
            # Short: profit when exit < entry
            gross_pnl = (self.entry_price - self.exit_price) * self.quantity
        else:
            # SELL, COVER, HEDGE_SELL - these are exit sides, PnL calculated from entry
            gross_pnl = (self.exit_price - self.entry_price) * self.quantity

        return gross_pnl - self.commission - self.fees

    @pnl.setter
    def pnl(self, value: float) -> None:
        """Allow manual PnL override if needed."""
        self._pnl = value

    @property
    def pnl_pct(self) -> float:
        """Calculate profit/loss percentage."""
        if not self.is_closed or self.entry_price == 0:
            return 0.0

        cost_basis = self.entry_price * self.quantity
        if cost_basis == 0:
            return 0.0

        return (self.pnl / cost_basis) * 100

    @property
    def pnl_aud(self) -> Optional[float]:
        """Calculate PnL in AUD if exchange rate available."""
        if self.exchange_rate is None:
            return None
        return self.pnl * self.exchange_rate

    @property
    def holding_duration(self) -> Optional[float]:
        """
        Calculate holding duration in seconds.

        Returns:
            Duration in seconds, or None if trade not closed
        """
        if not self.is_closed:
            return None
        return (self.exit_time - self.entry_time).total_seconds()

    @property
    def holding_minutes(self) -> Optional[int]:
        """Get holding duration in minutes."""
        duration = self.holding_duration
        if duration is None:
            return None
        return int(duration / 60)

    @property
    def holding_days(self) -> int:
        """Get holding duration in days."""
        if not self.is_closed:
            return 0
        return (self.exit_time - self.entry_time).days

    @property
    def total_value_usd(self) -> float:
        """Calculate total trade value in USD."""
        price = self.exit_price if self.is_closed else self.entry_price
        return self.quantity * price

    @property
    def total_value_aud(self) -> Optional[float]:
        """Calculate total trade value in AUD."""
        if self.exchange_rate is None:
            return None
        return self.total_value_usd * self.exchange_rate

    @property
    def day_range_pct(self) -> Optional[float]:
        """
        Calculate position in day's range.

        Returns:
            0% = at low, 100% = at high, None if data unavailable
        """
        if self.day_high is None or self.day_low is None:
            return None
        if self.day_high <= self.day_low:
            return None

        price = self.exit_price if self.is_closed else self.entry_price
        return ((price - self.day_low) / (self.day_high - self.day_low)) * 100

    @property
    def entry_time_aest(self) -> datetime:
        """Get entry time in AEST/AEDT timezone."""
        return self._to_aest(self.entry_time)

    @property
    def exit_time_aest(self) -> Optional[datetime]:
        """Get exit time in AEST/AEDT timezone."""
        if self.exit_time is None:
            return None
        return self._to_aest(self.exit_time)

    def _to_aest(self, dt: datetime) -> datetime:
        """Convert datetime to AEST."""
        utc_tz = pytz.UTC
        aest_tz = pytz.timezone(AEST_TIMEZONE)

        if dt.tzinfo is None:
            utc_time = utc_tz.localize(dt)
        else:
            utc_time = dt.astimezone(utc_tz)

        return utc_time.astimezone(aest_tz)

    def close(
        self,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        exit_reason: str = "",
        commission: float = 0.0,
    ) -> "TradeRecord":
        """
        Close the trade with exit details.

        Args:
            exit_price: Exit price
            exit_time: Exit timestamp (defaults to now)
            exit_reason: Reason for exit
            commission: Additional commission for exit

        Returns:
            Self for chaining
        """
        self.exit_price = exit_price
        self.exit_time = exit_time or datetime.utcnow()
        self.exit_reason = exit_reason
        self.commission += commission
        return self

    def to_dict(self) -> dict:
        """
        Convert to dictionary for JSON serialization.

        Compatible with existing trade log schema.
        """
        return {
            # Identifiers
            "trade_id": self.trade_id,
            "symbol": self.symbol,
            "side": self.side,
            "strategy": STRATEGY_NAME,

            # Quantities and prices
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "price": self.entry_price,  # Backward compatibility
            "fill_price": self.exit_price or self.entry_price,

            # Timestamps
            "entry_time": self.entry_time.isoformat(),
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "timestamp_utc": self.entry_time.isoformat(),
            "timestamp_aest": self.entry_time_aest.isoformat(),

            # P&L
            "pnl": self.pnl,
            "pnl_pct": self.pnl_pct,
            "realized_pnl_usd": self.pnl if self.is_closed else None,
            "realized_pnl_aud": self.pnl_aud,

            # Holding period
            "holding_days": self.holding_days,
            "holding_minutes": self.holding_minutes,
            "holding_period_days": self.holding_days,

            # Costs
            "commission": self.commission,
            "fees": self.fees,
            "slippage": self.slippage,

            # Order details
            "order_type": self.order_type,
            "order_id_alpaca": self.order_id_alpaca,
            "signal_reason": self.signal_reason,
            "exit_reason": self.exit_reason,
            "entry_reason": self.signal_reason,  # Backward compatibility

            # Values
            "total_value_usd": self.total_value_usd,
            "total_value_aud": self.total_value_aud,
            "exchange_rate": self.exchange_rate,

            # Indicator values
            "rsi_value": self.rsi_value,
            "vwap_value": self.vwap_value,
            "sma_value": self.sma_value,
            "atr_value": self.atr_value,
            "day_high": self.day_high,
            "day_low": self.day_low,
            "day_range_pct": self.day_range_pct,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TradeRecord":
        """
        Create TradeRecord from dictionary.

        Handles both new and legacy formats.
        """
        # Handle timestamp parsing
        entry_time = data.get("entry_time") or data.get("timestamp_utc")
        if isinstance(entry_time, str):
            entry_time = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))

        exit_time = data.get("exit_time")
        if isinstance(exit_time, str):
            exit_time = datetime.fromisoformat(exit_time.replace("Z", "+00:00"))

        return cls(
            trade_id=data.get("trade_id", str(uuid.uuid4())),
            symbol=data["symbol"],
            side=data["side"],
            quantity=data["quantity"],
            entry_price=data.get("entry_price") or data.get("price", 0),
            exit_price=data.get("exit_price"),
            entry_time=entry_time or datetime.utcnow(),
            exit_time=exit_time,
            order_type=data.get("order_type", "MARKET"),
            order_id_alpaca=data.get("order_id_alpaca", ""),
            signal_reason=data.get("signal_reason") or data.get("entry_reason", ""),
            exit_reason=data.get("exit_reason", ""),
            commission=data.get("commission", 0.0),
            fees=data.get("fees", 0.0),
            slippage=data.get("slippage", 0.0),
            rsi_value=data.get("rsi_value"),
            vwap_value=data.get("vwap_value"),
            sma_value=data.get("sma_value"),
            atr_value=data.get("atr_value"),
            day_high=data.get("day_high"),
            day_low=data.get("day_low"),
            exchange_rate=data.get("exchange_rate"),
        )

    @classmethod
    def from_signal(
        cls,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        signal: "Signal",
    ) -> "TradeRecord":
        """
        Create TradeRecord from a Signal object.

        Args:
            symbol: Trading symbol
            side: Trade side (BUY, SELL, etc.)
            quantity: Trade quantity
            price: Fill price
            signal: Signal object with indicator values

        Returns:
            New TradeRecord
        """
        return cls(
            symbol=symbol,
            side=side,
            quantity=quantity,
            entry_price=price,
            signal_reason=signal.reason,
            rsi_value=signal.rsi,
            vwap_value=getattr(signal, "vwap", None),
            sma_value=getattr(signal, "sma", None),
            day_high=getattr(signal, "day_high", None),
            day_low=getattr(signal, "day_low", None),
        )


class TradeRecordBuilder:
    """Builder pattern for creating TradeRecord instances."""

    def __init__(self, symbol: str, side: str):
        self._symbol = symbol
        self._side = side
        self._quantity: float = 0.0
        self._entry_price: float = 0.0
        self._exit_price: Optional[float] = None
        self._entry_time: datetime = datetime.utcnow()
        self._exit_time: Optional[datetime] = None
        self._order_type: str = "MARKET"
        self._order_id_alpaca: str = ""
        self._signal_reason: str = ""
        self._exit_reason: str = ""
        self._commission: float = 0.0
        self._fees: float = 0.0
        self._slippage: float = 0.0
        self._rsi_value: Optional[float] = None
        self._vwap_value: Optional[float] = None
        self._sma_value: Optional[float] = None
        self._atr_value: Optional[float] = None
        self._day_high: Optional[float] = None
        self._day_low: Optional[float] = None
        self._exchange_rate: Optional[float] = None

    def quantity(self, qty: float) -> "TradeRecordBuilder":
        self._quantity = qty
        return self

    def entry(self, price: float, time: Optional[datetime] = None) -> "TradeRecordBuilder":
        self._entry_price = price
        if time:
            self._entry_time = time
        return self

    def exit(self, price: float, time: Optional[datetime] = None) -> "TradeRecordBuilder":
        self._exit_price = price
        self._exit_time = time or datetime.utcnow()
        return self

    def order(
        self,
        order_type: str = "MARKET",
        alpaca_id: str = "",
    ) -> "TradeRecordBuilder":
        self._order_type = order_type
        self._order_id_alpaca = alpaca_id
        return self

    def reason(self, entry: str = "", exit: str = "") -> "TradeRecordBuilder":
        if entry:
            self._signal_reason = entry
        if exit:
            self._exit_reason = exit
        return self

    def costs(
        self,
        commission: float = 0.0,
        fees: float = 0.0,
        slippage: float = 0.0,
    ) -> "TradeRecordBuilder":
        self._commission = commission
        self._fees = fees
        self._slippage = slippage
        return self

    def indicators(
        self,
        rsi: Optional[float] = None,
        vwap: Optional[float] = None,
        sma: Optional[float] = None,
        atr: Optional[float] = None,
        day_high: Optional[float] = None,
        day_low: Optional[float] = None,
    ) -> "TradeRecordBuilder":
        self._rsi_value = rsi
        self._vwap_value = vwap
        self._sma_value = sma
        self._atr_value = atr
        self._day_high = day_high
        self._day_low = day_low
        return self

    def exchange_rate(self, rate: float) -> "TradeRecordBuilder":
        self._exchange_rate = rate
        return self

    def build(self) -> TradeRecord:
        """Build the TradeRecord instance."""
        return TradeRecord(
            symbol=self._symbol,
            side=self._side,
            quantity=self._quantity,
            entry_price=self._entry_price,
            exit_price=self._exit_price,
            entry_time=self._entry_time,
            exit_time=self._exit_time,
            order_type=self._order_type,
            order_id_alpaca=self._order_id_alpaca,
            signal_reason=self._signal_reason,
            exit_reason=self._exit_reason,
            commission=self._commission,
            fees=self._fees,
            slippage=self._slippage,
            rsi_value=self._rsi_value,
            vwap_value=self._vwap_value,
            sma_value=self._sma_value,
            atr_value=self._atr_value,
            day_high=self._day_high,
            day_low=self._day_low,
            exchange_rate=self._exchange_rate,
        )
