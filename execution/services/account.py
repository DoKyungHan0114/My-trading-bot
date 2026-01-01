"""
Account and position service.

Handles account queries and position management.
"""
import logging
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

# Try to import Alpaca
try:
    from alpaca.trading.client import TradingClient
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    TradingClient = None


class AccountService:
    """
    Service for account and position queries.

    Separated from order execution for single responsibility.
    """

    def __init__(
        self,
        client: Optional["TradingClient"] = None,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
        paper: bool = True,
    ):
        """
        Initialize account service.

        Args:
            client: Existing TradingClient (optional)
            api_key: Alpaca API key
            secret_key: Alpaca secret key
            paper: Use paper trading
        """
        self._client = client
        self._api_key = api_key
        self._secret_key = secret_key
        self._paper = paper

    @property
    def client(self) -> Optional["TradingClient"]:
        """Get or create trading client."""
        if not ALPACA_AVAILABLE:
            return None

        if self._client is None and self._api_key and self._secret_key:
            self._client = TradingClient(
                api_key=self._api_key,
                secret_key=self._secret_key,
                paper=self._paper,
            )
        return self._client

    def set_client(self, client: "TradingClient") -> None:
        """Set trading client."""
        self._client = client

    def get_account(self) -> Dict[str, Any]:
        """
        Get account information.

        Returns:
            Account details dictionary
        """
        if not self.client:
            return self._mock_account()

        try:
            account = self.client.get_account()
            return {
                "account_number": account.account_number,
                "status": account.status,
                "cash": float(account.cash),
                "buying_power": float(account.buying_power),
                "equity": float(account.equity),
                "portfolio_value": float(account.portfolio_value),
                "pattern_day_trader": account.pattern_day_trader,
                "trading_blocked": account.trading_blocked,
                "transfers_blocked": account.transfers_blocked,
            }
        except Exception as e:
            logger.error(f"Failed to get account: {e}")
            return self._mock_account()

    def _mock_account(self) -> Dict[str, Any]:
        """Return mock account for testing."""
        return {
            "account_number": "MOCK",
            "status": "ACTIVE",
            "cash": 10000.0,
            "buying_power": 10000.0,
            "equity": 10000.0,
            "portfolio_value": 10000.0,
            "pattern_day_trader": False,
            "trading_blocked": False,
            "transfers_blocked": False,
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Get all open positions.

        Returns:
            List of position dictionaries
        """
        if not self.client:
            return []

        try:
            positions = self.client.get_all_positions()
            return [self._position_to_dict(p) for p in positions]
        except Exception as e:
            logger.error(f"Failed to get positions: {e}")
            return []

    def get_position(self, symbol: str) -> Optional[Dict[str, Any]]:
        """
        Get position for a specific symbol.

        Args:
            symbol: Stock symbol

        Returns:
            Position dictionary or None
        """
        if not self.client:
            return None

        try:
            position = self.client.get_open_position(symbol)
            return self._position_to_dict(position)
        except Exception as e:
            logger.debug(f"No position found for {symbol}: {e}")
            return None

    def _position_to_dict(self, position) -> Dict[str, Any]:
        """Convert Alpaca position to dictionary."""
        return {
            "symbol": position.symbol,
            "quantity": float(position.qty),
            "avg_entry_price": float(position.avg_entry_price),
            "market_value": float(position.market_value),
            "cost_basis": float(position.cost_basis),
            "unrealized_pl": float(position.unrealized_pl),
            "unrealized_plpc": float(position.unrealized_plpc),
            "current_price": float(position.current_price),
            "side": getattr(position, "side", "long"),
        }

    def is_market_open(self) -> bool:
        """Check if market is currently open."""
        if not self.client:
            return True  # Assume open for testing

        try:
            clock = self.client.get_clock()
            return clock.is_open
        except Exception as e:
            logger.error(f"Failed to check market status: {e}")
            return False

    def get_market_clock(self) -> Optional[Dict[str, Any]]:
        """
        Get market clock information.

        Returns:
            Market clock details or None
        """
        if not self.client:
            return None

        try:
            clock = self.client.get_clock()
            return {
                "is_open": clock.is_open,
                "next_open": clock.next_open.isoformat() if clock.next_open else None,
                "next_close": clock.next_close.isoformat() if clock.next_close else None,
            }
        except Exception as e:
            logger.error(f"Failed to get market clock: {e}")
            return None
