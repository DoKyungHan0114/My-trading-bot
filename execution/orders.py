"""
Order classes and types.
"""
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config.constants import OrderSide, OrderStatus, OrderType


@dataclass
class Order:
    """Trading order representation."""
    symbol: str
    side: OrderSide
    quantity: float
    order_type: OrderType = OrderType.MARKET
    limit_price: Optional[float] = None
    order_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: OrderStatus = OrderStatus.PENDING
    created_at: datetime = field(default_factory=datetime.utcnow)
    filled_at: Optional[datetime] = None
    fill_price: Optional[float] = None
    filled_quantity: Optional[float] = None
    commission: float = 0.0
    fees: float = 0.0
    alpaca_order_id: Optional[str] = None
    signal_reason: str = ""

    @property
    def is_filled(self) -> bool:
        """Check if order is fully filled."""
        return self.status == OrderStatus.FILLED

    @property
    def is_pending(self) -> bool:
        """Check if order is pending."""
        return self.status == OrderStatus.PENDING

    @property
    def total_value(self) -> float:
        """Calculate total order value."""
        price = self.fill_price or self.limit_price or 0
        qty = self.filled_quantity or self.quantity
        return price * qty

    @property
    def slippage(self) -> float:
        """Calculate slippage if applicable."""
        if self.limit_price and self.fill_price:
            if self.side == OrderSide.BUY:
                return (self.fill_price - self.limit_price) / self.limit_price
            else:
                return (self.limit_price - self.fill_price) / self.limit_price
        return 0.0

    def fill(
        self,
        price: float,
        quantity: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Mark order as filled.

        Args:
            price: Fill price
            quantity: Filled quantity (defaults to order quantity)
            timestamp: Fill timestamp
        """
        self.status = OrderStatus.FILLED
        self.fill_price = price
        self.filled_quantity = quantity or self.quantity
        self.filled_at = timestamp or datetime.utcnow()

    def cancel(self) -> None:
        """Mark order as cancelled."""
        self.status = OrderStatus.CANCELLED

    def reject(self) -> None:
        """Mark order as rejected."""
        self.status = OrderStatus.REJECTED

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "order_id": self.order_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "order_type": self.order_type.value,
            "limit_price": self.limit_price,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "fill_price": self.fill_price,
            "filled_quantity": self.filled_quantity,
            "total_value": self.total_value,
            "commission": self.commission,
            "fees": self.fees,
            "slippage": self.slippage,
            "alpaca_order_id": self.alpaca_order_id,
            "signal_reason": self.signal_reason,
        }

    @classmethod
    def market_buy(
        cls,
        symbol: str,
        quantity: float,
        signal_reason: str = "",
    ) -> "Order":
        """Create a market buy order."""
        return cls(
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=quantity,
            order_type=OrderType.MARKET,
            signal_reason=signal_reason,
        )

    @classmethod
    def market_sell(
        cls,
        symbol: str,
        quantity: float,
        signal_reason: str = "",
    ) -> "Order":
        """Create a market sell order."""
        return cls(
            symbol=symbol,
            side=OrderSide.SELL,
            quantity=quantity,
            order_type=OrderType.MARKET,
            signal_reason=signal_reason,
        )


@dataclass
class Fill:
    """Order fill information."""
    order_id: str
    fill_price: float
    quantity: float
    timestamp: datetime
    commission: float = 0.0
    fees: float = 0.0

    @property
    def total_value(self) -> float:
        """Calculate total fill value."""
        return self.fill_price * self.quantity
