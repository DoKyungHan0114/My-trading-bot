"""
Core module containing shared abstractions.

This module contains unified classes that were previously duplicated across modules.
"""
from core.trade_record import TradeRecord, TradeRecordBuilder
from core.container import Container, get_container, ContainerScope

__all__ = [
    "TradeRecord",
    "TradeRecordBuilder",
    "Container",
    "get_container",
    "ContainerScope",
]
