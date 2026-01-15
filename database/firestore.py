"""
Firestore client for strategy versioning and trade logging.
"""
import logging
import os
from dataclasses import asdict
from datetime import datetime
from typing import Optional
from uuid import uuid4

try:
    from google.cloud import firestore
    from google.cloud.firestore_v1 import FieldFilter
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

from config.settings import StrategyConfig, get_settings

logger = logging.getLogger(__name__)


class FirestoreClient:
    """Firestore client for managing strategies, trades, and sessions."""

    def __init__(self, project_id: Optional[str] = None, prefix: Optional[str] = None):
        """
        Initialize Firestore client.

        Args:
            project_id: GCP project ID (uses env var if not provided)
            prefix: Collection name prefix (uses env var if not provided)
        """
        self.project_id = project_id or os.getenv("GOOGLE_CLOUD_PROJECT")
        self.prefix = prefix or os.getenv("FIRESTORE_COLLECTION_PREFIX", "tqqq")
        self._db: Optional[firestore.Client] = None

    @property
    def db(self) -> "firestore.Client":
        """Lazy initialize Firestore client."""
        if not FIRESTORE_AVAILABLE:
            raise ImportError(
                "google-cloud-firestore not installed. "
                "Run: pip install google-cloud-firestore"
            )
        if self._db is None:
            self._db = firestore.Client(project=self.project_id)
        return self._db

    def _collection(self, name: str) -> "firestore.CollectionReference":
        """Get prefixed collection reference."""
        return self.db.collection(f"{self.prefix}_{name}")

    # =========================================================================
    # STRATEGIES COLLECTION
    # =========================================================================

    def create_strategy(
        self,
        config: StrategyConfig,
        parent_id: Optional[str] = None,
        created_by: str = "system",
    ) -> str:
        """
        Create a new strategy version.

        Args:
            config: Strategy configuration
            parent_id: Parent strategy ID (for version tracking)
            created_by: Creator identifier

        Returns:
            New strategy ID
        """
        strategy_id = str(uuid4())
        doc = {
            "strategy_id": strategy_id,
            "parent_id": parent_id,
            "parameters": {
                # Core parameters
                "symbol": config.symbol,
                "rsi_period": config.rsi_period,
                "rsi_oversold": config.rsi_oversold,
                "rsi_overbought": config.rsi_overbought,
                "sma_period": config.sma_period,
                "stop_loss_pct": config.stop_loss_pct,
                "position_size_pct": config.position_size_pct,
                "cash_reserve_pct": config.cash_reserve_pct,
                # VWAP Filter
                "vwap_filter_enabled": config.vwap_filter_enabled,
                "vwap_entry_below": config.vwap_entry_below,
                # ATR Dynamic Stop Loss
                "atr_stop_enabled": config.atr_stop_enabled,
                "atr_stop_multiplier": config.atr_stop_multiplier,
                "atr_period": config.atr_period,
                # Bollinger Bands Filter
                "bb_filter_enabled": config.bb_filter_enabled,
                "bb_period": config.bb_period,
                "bb_std_dev": config.bb_std_dev,
                # Volume Filter
                "volume_filter_enabled": config.volume_filter_enabled,
                "volume_min_ratio": config.volume_min_ratio,
                "volume_avg_period": config.volume_avg_period,
                # Hedge (SQQQ) Parameters
                "short_enabled": config.short_enabled,
                "inverse_symbol": config.inverse_symbol,
                "use_inverse_etf": config.use_inverse_etf,
                "rsi_overbought_short": config.rsi_overbought_short,
                "rsi_oversold_short": config.rsi_oversold_short,
                "short_stop_loss_pct": config.short_stop_loss_pct,
                "short_position_size_pct": config.short_position_size_pct,
            },
            "created_at": datetime.utcnow(),
            "created_by": created_by,
            "is_active": True,
        }

        self._collection("strategies").document(strategy_id).set(doc)
        logger.info(f"Created strategy: {strategy_id}")
        return strategy_id

    def get_strategy(self, strategy_id: str) -> Optional[dict]:
        """Get strategy by ID."""
        doc = self._collection("strategies").document(strategy_id).get()
        if doc.exists:
            return doc.to_dict()
        return None

    def get_active_strategy(self) -> Optional[dict]:
        """Get the currently active strategy."""
        docs = (
            self._collection("strategies")
            .where(filter=FieldFilter("is_active", "==", True))
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(1)
            .stream()
        )
        for doc in docs:
            return doc.to_dict()
        return None

    def list_strategies(self, limit: int = 50) -> list[dict]:
        """List all strategies, newest first."""
        docs = (
            self._collection("strategies")
            .order_by("created_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    def deactivate_strategy(self, strategy_id: str) -> bool:
        """Deactivate a strategy."""
        try:
            self._collection("strategies").document(strategy_id).update(
                {"is_active": False}
            )
            return True
        except Exception as e:
            logger.error(f"Failed to deactivate strategy {strategy_id}: {e}")
            return False

    def activate_strategy(self, strategy_id: str) -> bool:
        """
        Activate a strategy and deactivate all others.

        Args:
            strategy_id: Strategy to activate

        Returns:
            True if successful
        """
        try:
            batch = self.db.batch()

            # Deactivate all active strategies
            active_docs = (
                self._collection("strategies")
                .where(filter=FieldFilter("is_active", "==", True))
                .stream()
            )
            for doc in active_docs:
                batch.update(doc.reference, {"is_active": False})

            # Activate target strategy
            batch.update(
                self._collection("strategies").document(strategy_id),
                {"is_active": True},
            )

            batch.commit()
            logger.info(f"Activated strategy: {strategy_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to activate strategy {strategy_id}: {e}")
            return False

    # =========================================================================
    # TRADES COLLECTION
    # =========================================================================

    def log_trade(
        self,
        strategy_id: str,
        symbol: str,
        side: str,
        entry_time: datetime,
        entry_price: float,
        quantity: float,
        exit_time: Optional[datetime] = None,
        exit_price: Optional[float] = None,
        pnl: Optional[float] = None,
        pnl_percent: Optional[float] = None,
    ) -> str:
        """
        Log a trade to Firestore.

        Args:
            strategy_id: Strategy that generated the trade
            symbol: Trading symbol
            side: BUY or SELL
            entry_time: Entry timestamp
            entry_price: Entry price
            quantity: Trade quantity
            exit_time: Exit timestamp (optional)
            exit_price: Exit price (optional)
            pnl: Profit/loss in USD (optional)
            pnl_percent: Profit/loss percentage (optional)

        Returns:
            Trade ID
        """
        trade_id = str(uuid4())
        doc = {
            "trade_id": trade_id,
            "strategy_id": strategy_id,
            "symbol": symbol,
            "side": side,
            "quantity": quantity,
            "entry_time": entry_time,
            "entry_price": entry_price,
            "exit_time": exit_time,
            "exit_price": exit_price,
            "pnl": pnl,
            "pnl_percent": pnl_percent,
            "created_at": datetime.utcnow(),
        }

        self._collection("trades").document(trade_id).set(doc)
        logger.info(f"Logged trade: {trade_id}")
        return trade_id

    def update_trade_exit(
        self,
        trade_id: str,
        exit_time: datetime,
        exit_price: float,
        pnl: float,
        pnl_percent: float,
    ) -> bool:
        """Update trade with exit information."""
        try:
            self._collection("trades").document(trade_id).update(
                {
                    "exit_time": exit_time,
                    "exit_price": exit_price,
                    "pnl": pnl,
                    "pnl_percent": pnl_percent,
                }
            )
            return True
        except Exception as e:
            logger.error(f"Failed to update trade {trade_id}: {e}")
            return False

    def get_trades_by_strategy(
        self, strategy_id: str, limit: int = 100
    ) -> list[dict]:
        """Get all trades for a strategy."""
        docs = (
            self._collection("trades")
            .where(filter=FieldFilter("strategy_id", "==", strategy_id))
            .order_by("entry_time", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    def get_trades_by_date(
        self, start_date: datetime, end_date: Optional[datetime] = None
    ) -> list[dict]:
        """Get trades within a date range."""
        query = self._collection("trades").where(
            filter=FieldFilter("entry_time", ">=", start_date)
        )
        if end_date:
            query = query.where(filter=FieldFilter("entry_time", "<=", end_date))

        docs = query.order_by(
            "entry_time", direction=firestore.Query.DESCENDING
        ).stream()
        return [doc.to_dict() for doc in docs]

    def get_todays_trades(self) -> list[dict]:
        """Get today's trades."""
        today_start = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        return self.get_trades_by_date(today_start)

    # =========================================================================
    # SESSIONS COLLECTION
    # =========================================================================

    def create_session(
        self,
        strategy_id: str,
        date: datetime,
        total_pnl: float,
        win_rate: float,
        max_drawdown: float,
        sharpe_ratio: float,
        trade_count: int,
        period_start: str = None,
        period_end: str = None,
        market_condition: dict = None,
    ) -> str:
        """
        Create a session performance record.

        Args:
            strategy_id: Strategy used in session
            date: Session date
            total_pnl: Total profit/loss
            win_rate: Win rate percentage
            max_drawdown: Maximum drawdown percentage
            sharpe_ratio: Sharpe ratio
            trade_count: Number of trades
            period_start: Backtest period start (YYYY-MM-DD)
            period_end: Backtest period end (YYYY-MM-DD)
            market_condition: Market regime metadata

        Returns:
            Session ID
        """
        session_id = str(uuid4())
        doc = {
            "session_id": session_id,
            "strategy_id": strategy_id,
            "date": date,
            "total_pnl": total_pnl,
            "win_rate": win_rate,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe_ratio,
            "trade_count": trade_count,
            "created_at": datetime.utcnow(),
        }
        if period_start:
            doc["period_start"] = period_start
        if period_end:
            doc["period_end"] = period_end
        if market_condition:
            doc["market_condition"] = market_condition

        self._collection("sessions").document(session_id).set(doc)
        logger.info(f"Created session: {session_id}")
        return session_id

    def get_sessions_by_strategy(
        self, strategy_id: str, limit: int = 7
    ) -> list[dict]:
        """Get session history for a strategy."""
        docs = (
            self._collection("sessions")
            .where(filter=FieldFilter("strategy_id", "==", strategy_id))
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    def get_recent_sessions(self, limit: int = 7) -> list[dict]:
        """Get recent sessions across all strategies."""
        docs = (
            self._collection("sessions")
            .order_by("date", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    # =========================================================================
    # STRATEGY CHANGES COLLECTION
    # =========================================================================

    def log_strategy_change(
        self,
        from_strategy_id: Optional[str],
        to_strategy_id: str,
        reason: str,
        report_snapshot: dict,
    ) -> str:
        """
        Log a strategy change event.

        Args:
            from_strategy_id: Previous strategy ID (None if first)
            to_strategy_id: New strategy ID
            reason: Reason for change
            report_snapshot: Performance report at time of change

        Returns:
            Change ID
        """
        change_id = str(uuid4())
        doc = {
            "change_id": change_id,
            "from_strategy_id": from_strategy_id,
            "to_strategy_id": to_strategy_id,
            "reason": reason,
            "report_snapshot": report_snapshot,
            "changed_at": datetime.utcnow(),
        }

        self._collection("strategy_changes").document(change_id).set(doc)
        logger.info(f"Logged strategy change: {change_id}")
        return change_id

    def get_strategy_changes(self, limit: int = 50) -> list[dict]:
        """Get strategy change history."""
        docs = (
            self._collection("strategy_changes")
            .order_by("changed_at", direction=firestore.Query.DESCENDING)
            .limit(limit)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    def get_changes_for_strategy(self, strategy_id: str) -> list[dict]:
        """Get all changes related to a strategy (as source or target)."""
        # Get changes where strategy is the target
        to_docs = (
            self._collection("strategy_changes")
            .where(filter=FieldFilter("to_strategy_id", "==", strategy_id))
            .stream()
        )

        # Get changes where strategy is the source
        from_docs = (
            self._collection("strategy_changes")
            .where(filter=FieldFilter("from_strategy_id", "==", strategy_id))
            .stream()
        )

        changes = [doc.to_dict() for doc in to_docs]
        changes.extend([doc.to_dict() for doc in from_docs])

        # Sort by changed_at descending
        changes.sort(key=lambda x: x["changed_at"], reverse=True)
        return changes

    def get_last_strategy_change_time(self) -> Optional[datetime]:
        """
        Get the timestamp of the most recent strategy change.
        Used for cooldown period enforcement.

        Returns:
            datetime of last change or None if no changes exist
        """
        try:
            docs = (
                self._collection("strategy_changes")
                .order_by("changed_at", direction=firestore.Query.DESCENDING)
                .limit(1)
                .stream()
            )
            for doc in docs:
                data = doc.to_dict()
                return data.get("changed_at")
            return None
        except Exception as e:
            logger.error(f"Failed to get last strategy change time: {e}")
            return None

    # =========================================================================
    # UTILITY METHODS
    # =========================================================================

    def strategy_to_config(self, strategy: dict) -> StrategyConfig:
        """Convert strategy document to StrategyConfig with all parameters."""
        params = strategy.get("parameters", {})
        return StrategyConfig(
            # Core parameters
            symbol=params.get("symbol", "TQQQ"),
            rsi_period=params.get("rsi_period", 2),
            rsi_oversold=params.get("rsi_oversold", 30.0),
            rsi_overbought=params.get("rsi_overbought", 75.0),
            sma_period=params.get("sma_period", 20),
            stop_loss_pct=params.get("stop_loss_pct", 0.05),
            position_size_pct=params.get("position_size_pct", 0.90),
            cash_reserve_pct=params.get("cash_reserve_pct", 0.10),
            # VWAP Filter (default enabled)
            vwap_filter_enabled=params.get("vwap_filter_enabled", True),
            vwap_entry_below=params.get("vwap_entry_below", True),
            # ATR Dynamic Stop Loss (default disabled)
            atr_stop_enabled=params.get("atr_stop_enabled", False),
            atr_stop_multiplier=params.get("atr_stop_multiplier", 2.0),
            atr_period=params.get("atr_period", 14),
            # Bollinger Bands Filter (default disabled)
            bb_filter_enabled=params.get("bb_filter_enabled", False),
            bb_period=params.get("bb_period", 20),
            bb_std_dev=params.get("bb_std_dev", 2.0),
            # Volume Filter (default disabled)
            volume_filter_enabled=params.get("volume_filter_enabled", False),
            volume_min_ratio=params.get("volume_min_ratio", 1.0),
            volume_avg_period=params.get("volume_avg_period", 20),
            # Hedge (SQQQ) Parameters
            short_enabled=params.get("short_enabled", True),
            inverse_symbol=params.get("inverse_symbol", "SQQQ"),
            use_inverse_etf=params.get("use_inverse_etf", True),
            rsi_overbought_short=params.get("rsi_overbought_short", 90.0),
            rsi_oversold_short=params.get("rsi_oversold_short", 60.0),
            short_stop_loss_pct=params.get("short_stop_loss_pct", 0.05),
            short_position_size_pct=params.get("short_position_size_pct", 0.30),
        )

    def health_check(self) -> bool:
        """Check Firestore connectivity."""
        try:
            # Try to list collections
            list(self.db.collections())
            return True
        except Exception as e:
            logger.error(f"Firestore health check failed: {e}")
            return False

    # =========================================================================
    # HEARTBEAT COLLECTION (for uptime tracking)
    # =========================================================================

    def record_heartbeat(
        self,
        status: str = "running",
        market_open: bool = False,
        signal_checked: bool = False,
        position: dict = None,
        error: str = None,
    ) -> str:
        """
        Record a bot heartbeat for uptime tracking.

        Args:
            status: Bot status (running, error, skipped)
            market_open: Whether market is open
            signal_checked: Whether signals were checked
            position: Current position info
            error: Error message if any

        Returns:
            Heartbeat ID
        """
        import pytz

        heartbeat_id = str(uuid4())
        now_utc = datetime.utcnow()

        # Use ET (US Eastern) for date to match trading day
        # This ensures heartbeats are grouped by trading day, not UTC day
        ET = pytz.timezone("America/New_York")
        now_et = datetime.now(ET)

        doc = {
            "heartbeat_id": heartbeat_id,
            "timestamp": now_utc,
            "date": now_et.strftime("%Y-%m-%d"),  # ET date for trading day
            "status": status,
            "market_open": market_open,
            "signal_checked": signal_checked,
            "position": position,
            "error": error,
        }

        self._collection("heartbeats").document(heartbeat_id).set(doc)
        logger.debug(f"Recorded heartbeat: {heartbeat_id}")
        return heartbeat_id

    def get_heartbeats_by_date(self, date: str) -> list[dict]:
        """
        Get all heartbeats for a specific date.

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            List of heartbeat documents
        """
        docs = (
            self._collection("heartbeats")
            .where(filter=FieldFilter("date", "==", date))
            .order_by("timestamp", direction=firestore.Query.ASCENDING)
            .stream()
        )
        return [doc.to_dict() for doc in docs]

    def get_heartbeat_count_by_date(self, date: str) -> dict:
        """
        Get heartbeat statistics for a specific date.

        Args:
            date: Date string (YYYY-MM-DD)

        Returns:
            Dict with total, market_open, signal_checked counts
        """
        heartbeats = self.get_heartbeats_by_date(date)

        total = len(heartbeats)
        market_open_count = sum(1 for h in heartbeats if h.get("market_open"))
        signal_checked_count = sum(1 for h in heartbeats if h.get("signal_checked"))
        error_count = sum(1 for h in heartbeats if h.get("error"))

        # Get first and last heartbeat times
        first_heartbeat = heartbeats[0]["timestamp"] if heartbeats else None
        last_heartbeat = heartbeats[-1]["timestamp"] if heartbeats else None

        return {
            "date": date,
            "total_heartbeats": total,
            "market_open_heartbeats": market_open_count,
            "signal_checked_heartbeats": signal_checked_count,
            "error_count": error_count,
            "first_heartbeat": first_heartbeat,
            "last_heartbeat": last_heartbeat,
        }

    def cleanup_old_heartbeats(self, days_to_keep: int = 7) -> int:
        """
        Delete heartbeats older than specified days.

        Args:
            days_to_keep: Number of days to keep

        Returns:
            Number of deleted documents
        """
        from datetime import timedelta

        cutoff = datetime.utcnow() - timedelta(days=days_to_keep)
        cutoff_str = cutoff.strftime("%Y-%m-%d")

        # Get old heartbeats
        old_docs = (
            self._collection("heartbeats")
            .where(filter=FieldFilter("date", "<", cutoff_str))
            .stream()
        )

        deleted = 0
        batch = self.db.batch()
        batch_count = 0

        for doc in old_docs:
            batch.delete(doc.reference)
            batch_count += 1
            deleted += 1

            # Firestore batch limit is 500
            if batch_count >= 500:
                batch.commit()
                batch = self.db.batch()
                batch_count = 0

        if batch_count > 0:
            batch.commit()

        logger.info(f"Cleaned up {deleted} old heartbeats")
        return deleted
