"""
Unified Logging Interface.

Consolidates logging functionality that was scattered across:
- trade_logger.py
- audit_trail.py
- daily_report.py
- weekly_report.py

Provides a single interface for all trade and system logging.
"""
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, Dict, Any, List, Protocol

try:
    from config.settings import LOGS_DIR
except ImportError:
    LOGS_DIR = Path(__file__).parent.parent / "logs"

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log severity levels."""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class EventType(Enum):
    """Types of loggable events."""
    # Trade events
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    TRADE_CANCELLED = "trade_cancelled"

    # Order events
    ORDER_SUBMITTED = "order_submitted"
    ORDER_FILLED = "order_filled"
    ORDER_REJECTED = "order_rejected"
    ORDER_CANCELLED = "order_cancelled"

    # Signal events
    SIGNAL_GENERATED = "signal_generated"
    SIGNAL_IGNORED = "signal_ignored"

    # System events
    SYSTEM_START = "system_start"
    SYSTEM_STOP = "system_stop"
    CONFIG_CHANGE = "config_change"
    ERROR = "error"

    # Strategy events
    STRATEGY_LOADED = "strategy_loaded"
    STRATEGY_UPDATED = "strategy_updated"


@dataclass
class LogEntry:
    """
    Unified log entry structure.

    All logs follow this structure for consistency.
    """
    timestamp: datetime
    event_type: EventType
    level: LogLevel
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    correlation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "level": self.level.value,
            "message": self.message,
            "data": self.data,
            "source": self.source,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LogEntry":
        """Create from dictionary."""
        return cls(
            timestamp=datetime.fromisoformat(data["timestamp"]),
            event_type=EventType(data["event_type"]),
            level=LogLevel(data["level"]),
            message=data["message"],
            data=data.get("data", {}),
            source=data.get("source", ""),
            correlation_id=data.get("correlation_id"),
        )


class LogHandler(Protocol):
    """Protocol for log handlers."""

    def handle(self, entry: LogEntry) -> None:
        """Handle a log entry."""
        ...


class FileLogHandler:
    """Handler that writes logs to JSON files."""

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        filename: str = "events.json",
        max_entries: int = 10000,
    ):
        self.log_dir = log_dir or LOGS_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.log_dir / filename
        self.max_entries = max_entries
        self._entries: List[Dict[str, Any]] = []
        self._load_existing()

    def _load_existing(self) -> None:
        """Load existing log entries."""
        if self.log_file.exists():
            try:
                with open(self.log_file, "r") as f:
                    self._entries = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load existing logs: {e}")
                self._entries = []

    def _save(self) -> None:
        """Save entries to file."""
        try:
            # Trim if too many entries
            if len(self._entries) > self.max_entries:
                self._entries = self._entries[-self.max_entries:]

            with open(self.log_file, "w") as f:
                json.dump(self._entries, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save logs: {e}")

    def handle(self, entry: LogEntry) -> None:
        """Handle a log entry by writing to file."""
        self._entries.append(entry.to_dict())
        self._save()

    def get_entries(
        self,
        event_type: Optional[EventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> List[LogEntry]:
        """Query log entries with filters."""
        entries = self._entries

        if event_type:
            entries = [e for e in entries if e["event_type"] == event_type.value]

        if start_time:
            start_str = start_time.isoformat()
            entries = [e for e in entries if e["timestamp"] >= start_str]

        if end_time:
            end_str = end_time.isoformat()
            entries = [e for e in entries if e["timestamp"] <= end_str]

        # Return most recent entries
        entries = entries[-limit:]
        return [LogEntry.from_dict(e) for e in entries]


class ConsoleLogHandler:
    """Handler that writes logs to console."""

    def __init__(self, min_level: LogLevel = LogLevel.INFO):
        self.min_level = min_level
        self._level_order = [LogLevel.DEBUG, LogLevel.INFO, LogLevel.WARNING, LogLevel.ERROR, LogLevel.CRITICAL]

    def handle(self, entry: LogEntry) -> None:
        """Handle a log entry by writing to console."""
        if self._level_order.index(entry.level) < self._level_order.index(self.min_level):
            return

        log_func = getattr(logger, entry.level.value)
        log_func(f"[{entry.event_type.value}] {entry.message}")


class UnifiedLogger:
    """
    Unified logging interface.

    Consolidates all logging through a single interface with
    pluggable handlers for different outputs.
    """

    def __init__(self, source: str = ""):
        self.source = source
        self._handlers: List[LogHandler] = []

    def add_handler(self, handler: LogHandler) -> "UnifiedLogger":
        """Add a log handler."""
        self._handlers.append(handler)
        return self

    def remove_handler(self, handler: LogHandler) -> None:
        """Remove a log handler."""
        if handler in self._handlers:
            self._handlers.remove(handler)

    def _log(
        self,
        event_type: EventType,
        level: LogLevel,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        correlation_id: Optional[str] = None,
    ) -> LogEntry:
        """Create and dispatch a log entry."""
        entry = LogEntry(
            timestamp=datetime.utcnow(),
            event_type=event_type,
            level=level,
            message=message,
            data=data or {},
            source=self.source,
            correlation_id=correlation_id,
        )

        for handler in self._handlers:
            try:
                handler.handle(entry)
            except Exception as e:
                logger.error(f"Handler error: {e}")

        return entry

    # =========================================================================
    # Trade Logging
    # =========================================================================

    def log_trade_entry(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        reason: str = "",
        **extra,
    ) -> LogEntry:
        """Log a trade entry."""
        return self._log(
            EventType.TRADE_ENTRY,
            LogLevel.INFO,
            f"{side} {quantity:.4f} {symbol} @ ${price:.2f}",
            data={
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "reason": reason,
                **extra,
            },
        )

    def log_trade_exit(
        self,
        symbol: str,
        side: str,
        quantity: float,
        price: float,
        pnl: float,
        pnl_pct: float,
        reason: str = "",
        **extra,
    ) -> LogEntry:
        """Log a trade exit."""
        return self._log(
            EventType.TRADE_EXIT,
            LogLevel.INFO,
            f"{side} {quantity:.4f} {symbol} @ ${price:.2f}, PnL: ${pnl:+.2f} ({pnl_pct:+.2f}%)",
            data={
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                "pnl": pnl,
                "pnl_pct": pnl_pct,
                "reason": reason,
                **extra,
            },
        )

    # =========================================================================
    # Order Logging
    # =========================================================================

    def log_order_submitted(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        order_type: str = "MARKET",
        **extra,
    ) -> LogEntry:
        """Log an order submission."""
        return self._log(
            EventType.ORDER_SUBMITTED,
            LogLevel.INFO,
            f"Order submitted: {side} {quantity:.4f} {symbol} ({order_type})",
            data={
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "order_type": order_type,
                **extra,
            },
        )

    def log_order_filled(
        self,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        fill_price: float,
        **extra,
    ) -> LogEntry:
        """Log an order fill."""
        return self._log(
            EventType.ORDER_FILLED,
            LogLevel.INFO,
            f"Order filled: {side} {quantity:.4f} {symbol} @ ${fill_price:.2f}",
            data={
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "fill_price": fill_price,
                **extra,
            },
        )

    def log_order_rejected(
        self,
        order_id: str,
        symbol: str,
        reason: str = "",
        **extra,
    ) -> LogEntry:
        """Log an order rejection."""
        return self._log(
            EventType.ORDER_REJECTED,
            LogLevel.WARNING,
            f"Order rejected: {symbol} - {reason}",
            data={
                "order_id": order_id,
                "symbol": symbol,
                "reason": reason,
                **extra,
            },
        )

    # =========================================================================
    # Signal Logging
    # =========================================================================

    def log_signal(
        self,
        signal_type: str,
        symbol: str,
        price: float,
        reason: str,
        **extra,
    ) -> LogEntry:
        """Log a trading signal."""
        return self._log(
            EventType.SIGNAL_GENERATED,
            LogLevel.INFO,
            f"{signal_type} signal: {symbol} @ ${price:.2f}",
            data={
                "signal_type": signal_type,
                "symbol": symbol,
                "price": price,
                "reason": reason,
                **extra,
            },
        )

    # =========================================================================
    # System Logging
    # =========================================================================

    def log_system_start(self, mode: str = "", **extra) -> LogEntry:
        """Log system start."""
        return self._log(
            EventType.SYSTEM_START,
            LogLevel.INFO,
            f"System started in {mode} mode" if mode else "System started",
            data={"mode": mode, **extra},
        )

    def log_system_stop(self, reason: str = "", **extra) -> LogEntry:
        """Log system stop."""
        return self._log(
            EventType.SYSTEM_STOP,
            LogLevel.INFO,
            f"System stopped: {reason}" if reason else "System stopped",
            data={"reason": reason, **extra},
        )

    def log_error(
        self,
        error: Exception,
        context: str = "",
        **extra,
    ) -> LogEntry:
        """Log an error."""
        return self._log(
            EventType.ERROR,
            LogLevel.ERROR,
            f"Error in {context}: {type(error).__name__}: {error}",
            data={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
                **extra,
            },
        )

    def log_config_change(
        self,
        changes: Dict[str, Any],
        source: str = "",
        **extra,
    ) -> LogEntry:
        """Log a configuration change."""
        return self._log(
            EventType.CONFIG_CHANGE,
            LogLevel.INFO,
            f"Configuration changed from {source}" if source else "Configuration changed",
            data={"changes": changes, "source": source, **extra},
        )


def create_default_logger(source: str = "trading_bot") -> UnifiedLogger:
    """
    Create a logger with default handlers.

    Args:
        source: Source identifier for log entries

    Returns:
        Configured UnifiedLogger instance
    """
    logger = UnifiedLogger(source=source)
    logger.add_handler(FileLogHandler(filename="events.json"))
    logger.add_handler(ConsoleLogHandler())
    return logger


# Singleton instance for convenience
_default_logger: Optional[UnifiedLogger] = None


def get_logger(source: str = "trading_bot") -> UnifiedLogger:
    """Get or create the default logger instance."""
    global _default_logger
    if _default_logger is None:
        _default_logger = create_default_logger(source)
    return _default_logger
