"""Logging system module."""
from logging_system.trade_logger import TradeLogger, TradeLog, ExchangeRateService
from logging_system.tax_reporter import ATOTaxReporter
from logging_system.audit_trail import AuditTrail, AuditEventType, AuditEntry
from logging_system.unified_logger import (
    UnifiedLogger,
    LogEntry,
    LogLevel,
    EventType,
    FileLogHandler,
    ConsoleLogHandler,
    create_default_logger,
    get_logger,
)

__all__ = [
    # Legacy exports (for backward compatibility)
    "TradeLogger",
    "TradeLog",
    "ExchangeRateService",
    "ATOTaxReporter",
    "AuditTrail",
    "AuditEventType",
    "AuditEntry",
    # New unified logging
    "UnifiedLogger",
    "LogEntry",
    "LogLevel",
    "EventType",
    "FileLogHandler",
    "ConsoleLogHandler",
    "create_default_logger",
    "get_logger",
]
