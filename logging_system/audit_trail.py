"""
Audit trail for system events and compliance.
"""
import json
import logging
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from config.settings import LOGS_DIR

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events."""
    SYSTEM_START = "SYSTEM_START"
    SYSTEM_STOP = "SYSTEM_STOP"
    ORDER_CREATED = "ORDER_CREATED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_FILLED = "ORDER_FILLED"
    ORDER_CANCELLED = "ORDER_CANCELLED"
    ORDER_REJECTED = "ORDER_REJECTED"
    POSITION_OPENED = "POSITION_OPENED"
    POSITION_CLOSED = "POSITION_CLOSED"
    SIGNAL_GENERATED = "SIGNAL_GENERATED"
    RISK_LIMIT_TRIGGERED = "RISK_LIMIT_TRIGGERED"
    ERROR = "ERROR"
    WARNING = "WARNING"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    API_CALL = "API_CALL"
    BACKTEST_START = "BACKTEST_START"
    BACKTEST_END = "BACKTEST_END"


class AuditEntry:
    """Single audit log entry."""

    def __init__(
        self,
        event_type: AuditEventType,
        message: str,
        data: Optional[dict] = None,
        source: str = "system",
    ):
        self.timestamp = datetime.utcnow()
        self.event_type = event_type
        self.message = message
        self.data = data or {}
        self.source = source

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "message": self.message,
            "data": self.data,
            "source": self.source,
        }

    def to_json(self) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), default=str)


class AuditTrail:
    """Audit trail logger for compliance and debugging."""

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        max_entries: int = 10000,
    ):
        """
        Initialize audit trail.

        Args:
            log_dir: Directory for audit logs
            max_entries: Maximum entries to keep in memory
        """
        self.log_dir = log_dir or LOGS_DIR
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_entries = max_entries
        self._entries: list[dict] = []
        self._current_log_file = self._get_log_file()

    def _get_log_file(self) -> Path:
        """Get current log file path."""
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        return self.log_dir / f"audit_{date_str}.jsonl"

    def log(
        self,
        event_type: AuditEventType,
        message: str,
        data: Optional[dict] = None,
        source: str = "system",
    ) -> AuditEntry:
        """
        Log an audit event.

        Args:
            event_type: Type of event
            message: Human-readable message
            data: Additional event data
            source: Event source

        Returns:
            Created audit entry
        """
        entry = AuditEntry(
            event_type=event_type,
            message=message,
            data=data,
            source=source,
        )

        # Add to memory
        self._entries.append(entry.to_dict())
        if len(self._entries) > self.max_entries:
            self._entries = self._entries[-self.max_entries:]

        # Write to file
        self._write_entry(entry)

        # Log to standard logger
        log_level = logging.ERROR if event_type == AuditEventType.ERROR else logging.INFO
        logger.log(log_level, f"[AUDIT] {event_type.value}: {message}")

        return entry

    def _write_entry(self, entry: AuditEntry) -> None:
        """Write entry to log file."""
        # Check if we need a new log file (new day)
        current_file = self._get_log_file()
        if current_file != self._current_log_file:
            self._current_log_file = current_file

        try:
            with open(self._current_log_file, "a") as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}")

    def log_order(
        self,
        event_type: AuditEventType,
        order_id: str,
        symbol: str,
        side: str,
        quantity: float,
        price: Optional[float] = None,
        **kwargs,
    ) -> AuditEntry:
        """Log order-related event."""
        return self.log(
            event_type=event_type,
            message=f"{event_type.value}: {side} {quantity} {symbol}",
            data={
                "order_id": order_id,
                "symbol": symbol,
                "side": side,
                "quantity": quantity,
                "price": price,
                **kwargs,
            },
            source="order_manager",
        )

    def log_signal(
        self,
        signal_type: str,
        symbol: str,
        price: float,
        reason: str,
    ) -> AuditEntry:
        """Log signal generation."""
        return self.log(
            event_type=AuditEventType.SIGNAL_GENERATED,
            message=f"Signal: {signal_type} {symbol} @ ${price:.2f}",
            data={
                "signal_type": signal_type,
                "symbol": symbol,
                "price": price,
                "reason": reason,
            },
            source="signal_generator",
        )

    def log_error(
        self,
        error: Exception,
        context: str = "",
    ) -> AuditEntry:
        """Log error event."""
        return self.log(
            event_type=AuditEventType.ERROR,
            message=f"{context}: {str(error)}" if context else str(error),
            data={
                "error_type": type(error).__name__,
                "error_message": str(error),
                "context": context,
            },
            source="error_handler",
        )

    def log_api_call(
        self,
        endpoint: str,
        method: str = "GET",
        status: Optional[int] = None,
        latency_ms: Optional[float] = None,
    ) -> AuditEntry:
        """Log API call."""
        return self.log(
            event_type=AuditEventType.API_CALL,
            message=f"API: {method} {endpoint}",
            data={
                "endpoint": endpoint,
                "method": method,
                "status": status,
                "latency_ms": latency_ms,
            },
            source="api_client",
        )

    def get_entries(
        self,
        event_type: Optional[AuditEventType] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get audit entries with filters.

        Args:
            event_type: Filter by event type
            start_time: Filter from this time
            end_time: Filter to this time
            limit: Maximum entries to return

        Returns:
            List of matching entries
        """
        entries = self._entries

        if event_type:
            entries = [e for e in entries if e["event_type"] == event_type.value]

        if start_time:
            start_str = start_time.isoformat()
            entries = [e for e in entries if e["timestamp"] >= start_str]

        if end_time:
            end_str = end_time.isoformat()
            entries = [e for e in entries if e["timestamp"] <= end_str]

        return entries[-limit:]

    def get_errors(self, limit: int = 50) -> list[dict]:
        """Get recent error entries."""
        return self.get_entries(event_type=AuditEventType.ERROR, limit=limit)

    def clear_memory(self) -> None:
        """Clear in-memory entries (files remain)."""
        self._entries = []
