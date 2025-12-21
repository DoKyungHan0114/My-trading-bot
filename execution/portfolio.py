"""
Portfolio state management.
"""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from config.constants import OrderSide

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Single position in a symbol."""
    symbol: str
    quantity: float
    avg_entry_price: float
    entry_date: datetime
    current_price: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)

    @property
    def market_value(self) -> float:
        """Current market value of position."""
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float:
        """Total cost basis."""
        return self.quantity * self.avg_entry_price

    @property
    def unrealized_pnl(self) -> float:
        """Unrealized profit/loss."""
        return self.market_value - self.cost_basis

    @property
    def unrealized_pnl_pct(self) -> float:
        """Unrealized P&L percentage."""
        if self.cost_basis == 0:
            return 0.0
        return (self.unrealized_pnl / self.cost_basis) * 100

    @property
    def holding_days(self) -> int:
        """Number of days holding position."""
        return (datetime.utcnow() - self.entry_date).days

    def update_price(self, price: float) -> None:
        """Update current price."""
        self.current_price = price
        self.last_updated = datetime.utcnow()

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "symbol": self.symbol,
            "quantity": self.quantity,
            "avg_entry_price": self.avg_entry_price,
            "entry_date": self.entry_date.isoformat(),
            "current_price": self.current_price,
            "market_value": self.market_value,
            "cost_basis": self.cost_basis,
            "unrealized_pnl": self.unrealized_pnl,
            "unrealized_pnl_pct": self.unrealized_pnl_pct,
            "holding_days": self.holding_days,
        }


@dataclass
class Portfolio:
    """Portfolio state and management."""
    initial_capital: float
    cash: float = field(init=False)
    positions: dict[str, Position] = field(default_factory=dict)
    realized_pnl: float = 0.0
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    def __post_init__(self):
        """Initialize cash to initial capital."""
        self.cash = self.initial_capital

    @property
    def equity(self) -> float:
        """Total portfolio equity (cash + positions)."""
        positions_value = sum(p.market_value for p in self.positions.values())
        return self.cash + positions_value

    @property
    def total_return(self) -> float:
        """Total return since inception."""
        return self.equity - self.initial_capital

    @property
    def total_return_pct(self) -> float:
        """Total return percentage."""
        if self.initial_capital == 0:
            return 0.0
        return (self.total_return / self.initial_capital) * 100

    @property
    def unrealized_pnl(self) -> float:
        """Total unrealized P&L."""
        return sum(p.unrealized_pnl for p in self.positions.values())

    @property
    def win_rate(self) -> float:
        """Win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100

    @property
    def has_position(self) -> bool:
        """Check if any position is open."""
        return len(self.positions) > 0

    def get_position(self, symbol: str) -> Optional[Position]:
        """Get position for symbol."""
        return self.positions.get(symbol)

    def open_position(
        self,
        symbol: str,
        quantity: float,
        price: float,
        timestamp: Optional[datetime] = None,
        commission: float = 0.0,
    ) -> Position:
        """
        Open or add to a position.

        Args:
            symbol: Stock symbol
            quantity: Number of shares
            price: Entry price
            timestamp: Entry timestamp
            commission: Commission paid

        Returns:
            Updated position
        """
        cost = quantity * price + commission

        if cost > self.cash:
            raise ValueError(f"Insufficient cash: ${self.cash:.2f} < ${cost:.2f}")

        self.cash -= cost

        if symbol in self.positions:
            # Average into existing position
            pos = self.positions[symbol]
            total_qty = pos.quantity + quantity
            total_cost = pos.cost_basis + (quantity * price)
            pos.avg_entry_price = total_cost / total_qty
            pos.quantity = total_qty
        else:
            # New position
            self.positions[symbol] = Position(
                symbol=symbol,
                quantity=quantity,
                avg_entry_price=price,
                entry_date=timestamp or datetime.utcnow(),
                current_price=price,
            )

        logger.info(
            f"Opened position: {quantity:.4f} {symbol} @ ${price:.2f} "
            f"(Cash: ${self.cash:.2f})"
        )

        return self.positions[symbol]

    def close_position(
        self,
        symbol: str,
        price: float,
        quantity: Optional[float] = None,
        timestamp: Optional[datetime] = None,
        commission: float = 0.0,
    ) -> float:
        """
        Close or reduce a position.

        Args:
            symbol: Stock symbol
            price: Exit price
            quantity: Shares to sell (None = all)
            timestamp: Exit timestamp
            commission: Commission paid

        Returns:
            Realized P&L
        """
        if symbol not in self.positions:
            raise ValueError(f"No position in {symbol}")

        pos = self.positions[symbol]
        sell_qty = quantity or pos.quantity

        if sell_qty > pos.quantity:
            raise ValueError(
                f"Cannot sell {sell_qty} shares, only {pos.quantity} held"
            )

        # Calculate realized P&L
        proceeds = sell_qty * price - commission
        cost_basis = sell_qty * pos.avg_entry_price
        realized = proceeds - cost_basis

        self.cash += proceeds
        self.realized_pnl += realized
        self.total_trades += 1

        if realized > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        # Update or remove position
        if sell_qty >= pos.quantity:
            del self.positions[symbol]
        else:
            pos.quantity -= sell_qty

        logger.info(
            f"Closed position: {sell_qty:.4f} {symbol} @ ${price:.2f}, "
            f"P&L: ${realized:.2f} ({realized/cost_basis*100:.1f}%)"
        )

        return realized

    def update_prices(self, prices: dict[str, float]) -> None:
        """
        Update current prices for all positions.

        Args:
            prices: Dictionary of symbol -> price
        """
        for symbol, position in self.positions.items():
            if symbol in prices:
                position.update_price(prices[symbol])

    def get_buying_power(self) -> float:
        """Get available buying power."""
        return self.cash

    def get_summary(self) -> dict:
        """Get portfolio summary."""
        return {
            "initial_capital": self.initial_capital,
            "cash": self.cash,
            "equity": self.equity,
            "total_return": self.total_return,
            "total_return_pct": self.total_return_pct,
            "realized_pnl": self.realized_pnl,
            "unrealized_pnl": self.unrealized_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": self.win_rate,
            "positions": {k: v.to_dict() for k, v in self.positions.items()},
        }

    def reset(self) -> None:
        """Reset portfolio to initial state."""
        self.cash = self.initial_capital
        self.positions.clear()
        self.realized_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.losing_trades = 0
