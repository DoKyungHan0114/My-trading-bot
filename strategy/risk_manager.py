"""
Risk management and position sizing.
"""
import logging
from dataclasses import dataclass
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


@dataclass
class PositionSize:
    """Position sizing result."""
    shares: float
    dollar_amount: float
    percentage_of_account: float
    risk_amount: float


class RiskManager:
    """Manage position sizing and risk controls."""

    def __init__(
        self,
        position_size_pct: Optional[float] = None,
        cash_reserve_pct: Optional[float] = None,
        stop_loss_pct: Optional[float] = None,
        max_position_value: Optional[float] = None,
    ):
        """
        Initialize risk manager.

        Args:
            position_size_pct: Percentage of account for positions
            cash_reserve_pct: Percentage to keep as cash reserve
            stop_loss_pct: Stop loss percentage
            max_position_value: Maximum position value (optional cap)
        """
        settings = get_settings()
        self.position_size_pct = position_size_pct or settings.strategy.position_size_pct
        self.cash_reserve_pct = cash_reserve_pct or settings.strategy.cash_reserve_pct
        self.stop_loss_pct = stop_loss_pct or settings.strategy.stop_loss_pct
        self.max_position_value = max_position_value

    def calculate_position_size(
        self,
        account_value: float,
        current_price: float,
        use_fractional: bool = True,
    ) -> PositionSize:
        """
        Calculate position size based on account value and risk parameters.

        Args:
            account_value: Total account value
            current_price: Current price of the asset
            use_fractional: Whether to use fractional shares

        Returns:
            PositionSize with calculated values
        """
        # Calculate available capital (account - cash reserve)
        available_capital = account_value * self.position_size_pct

        # Apply maximum position cap if set
        if self.max_position_value:
            available_capital = min(available_capital, self.max_position_value)

        # Calculate shares
        if use_fractional:
            shares = available_capital / current_price
        else:
            shares = int(available_capital / current_price)

        dollar_amount = shares * current_price
        pct_of_account = (dollar_amount / account_value) * 100 if account_value > 0 else 0
        risk_amount = dollar_amount * self.stop_loss_pct

        logger.info(
            f"Position size: {shares:.4f} shares @ ${current_price:.2f} = "
            f"${dollar_amount:.2f} ({pct_of_account:.1f}% of account)"
        )

        return PositionSize(
            shares=shares,
            dollar_amount=dollar_amount,
            percentage_of_account=pct_of_account,
            risk_amount=risk_amount,
        )

    def validate_trade(
        self,
        account_value: float,
        position_value: float,
        buying_power: float,
    ) -> tuple[bool, str]:
        """
        Validate if a trade can be executed.

        Args:
            account_value: Total account value
            position_value: Proposed position value
            buying_power: Available buying power

        Returns:
            Tuple of (is_valid, reason)
        """
        # Check buying power
        if position_value > buying_power:
            return False, f"Insufficient buying power: ${buying_power:.2f} < ${position_value:.2f}"

        # Check position size limit
        max_position = account_value * self.position_size_pct
        if position_value > max_position * 1.01:  # 1% tolerance
            return False, f"Position exceeds limit: ${position_value:.2f} > ${max_position:.2f}"

        # Check minimum position
        min_position = 1.0  # Minimum $1 position
        if position_value < min_position:
            return False, f"Position too small: ${position_value:.2f} < ${min_position:.2f}"

        return True, "Trade validated"

    def calculate_stop_loss_price(
        self,
        entry_price: float,
        side: str = "long",
    ) -> float:
        """
        Calculate stop loss price.

        Args:
            entry_price: Entry price
            side: Position side (long/short)

        Returns:
            Stop loss price
        """
        if side.lower() == "long":
            return entry_price * (1 - self.stop_loss_pct)
        else:
            return entry_price * (1 + self.stop_loss_pct)

    def check_stop_loss(
        self,
        current_price: float,
        entry_price: float,
        side: str = "long",
    ) -> tuple[bool, float]:
        """
        Check if stop loss is triggered.

        Args:
            current_price: Current market price
            entry_price: Entry price
            side: Position side

        Returns:
            Tuple of (is_triggered, loss_percentage)
        """
        if side.lower() == "long":
            pnl_pct = (current_price - entry_price) / entry_price
            triggered = pnl_pct <= -self.stop_loss_pct
        else:
            pnl_pct = (entry_price - current_price) / entry_price
            triggered = pnl_pct <= -self.stop_loss_pct

        return triggered, pnl_pct

    def get_risk_metrics(
        self,
        account_value: float,
        position_value: float,
        unrealized_pnl: float,
    ) -> dict:
        """
        Calculate current risk metrics.

        Args:
            account_value: Total account value
            position_value: Current position value
            unrealized_pnl: Unrealized P&L

        Returns:
            Dictionary of risk metrics
        """
        position_pct = (position_value / account_value * 100) if account_value > 0 else 0
        cash_pct = 100 - position_pct
        pnl_pct = (unrealized_pnl / account_value * 100) if account_value > 0 else 0

        return {
            "account_value": account_value,
            "position_value": position_value,
            "position_pct": position_pct,
            "cash_pct": cash_pct,
            "unrealized_pnl": unrealized_pnl,
            "unrealized_pnl_pct": pnl_pct,
            "max_loss_at_stop": position_value * self.stop_loss_pct,
        }
