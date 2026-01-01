"""
Dependency Injection Container.

Provides centralized management of application dependencies,
replacing the scattered get_settings() calls throughout the codebase.

Usage:
    from core.container import Container

    # Get singleton container
    container = Container.instance()

    # Access settings
    settings = container.settings

    # Access services (lazy initialized)
    broker = container.broker
    signal_generator = container.signal_generator
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, TypeVar, Generic, Callable, Dict, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Lazy(Generic[T]):
    """
    Lazy initialization wrapper.

    Defers creation of an object until first access.
    """

    def __init__(self, factory: Callable[[], T]):
        self._factory = factory
        self._instance: Optional[T] = None
        self._initialized = False

    @property
    def value(self) -> T:
        """Get or create the instance."""
        if not self._initialized:
            self._instance = self._factory()
            self._initialized = True
        return self._instance

    def reset(self) -> None:
        """Reset to uninitialized state."""
        self._instance = None
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        return self._initialized


@dataclass
class Container:
    """
    Dependency Injection Container.

    Centralizes all application dependencies and their configuration.
    Services are lazily initialized on first access.
    """

    _instance: Optional["Container"] = field(default=None, repr=False, init=False)

    # Configuration
    _settings: Optional[Any] = field(default=None, repr=False)
    _overrides: Dict[str, Any] = field(default_factory=dict, repr=False)

    # Lazy service factories
    _services: Dict[str, Lazy] = field(default_factory=dict, repr=False)

    def __post_init__(self):
        """Initialize lazy service factories."""
        self._register_default_factories()

    @classmethod
    def instance(cls) -> "Container":
        """Get singleton container instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset singleton instance (for testing)."""
        cls._instance = None

    @classmethod
    def configure(cls, **overrides) -> "Container":
        """
        Configure container with overrides.

        Args:
            **overrides: Service overrides (e.g., settings=custom_settings)

        Returns:
            Configured container instance
        """
        container = cls.instance()
        container._overrides.update(overrides)
        return container

    def _register_default_factories(self) -> None:
        """Register default lazy factories for services."""
        # Settings
        self._services["settings"] = Lazy(self._create_settings)

        # Data services
        self._services["data_fetcher"] = Lazy(self._create_data_fetcher)
        self._services["data_storage"] = Lazy(self._create_data_storage)

        # Strategy services
        self._services["signal_generator"] = Lazy(self._create_signal_generator)
        self._services["risk_manager"] = Lazy(self._create_risk_manager)

        # Execution services
        self._services["broker"] = Lazy(self._create_broker)

        # Logging services
        self._services["trade_logger"] = Lazy(self._create_trade_logger)
        self._services["audit_trail"] = Lazy(self._create_audit_trail)

        # Notification services
        self._services["discord"] = Lazy(self._create_discord)

    # =========================================================================
    # Settings
    # =========================================================================

    @property
    def settings(self):
        """Get application settings."""
        if "settings" in self._overrides:
            return self._overrides["settings"]
        return self._services["settings"].value

    def _create_settings(self):
        """Create settings instance."""
        from config.settings import get_settings
        return get_settings()

    # =========================================================================
    # Strategy Settings Shortcuts
    # =========================================================================

    @property
    def strategy_config(self):
        """Get strategy configuration."""
        return self.settings.strategy

    @property
    def symbol(self) -> str:
        """Get trading symbol."""
        return self.settings.strategy.symbol

    @property
    def inverse_symbol(self) -> str:
        """Get inverse ETF symbol."""
        return self.settings.strategy.inverse_symbol

    # =========================================================================
    # Data Services
    # =========================================================================

    @property
    def data_fetcher(self):
        """Get data fetcher instance."""
        if "data_fetcher" in self._overrides:
            return self._overrides["data_fetcher"]
        return self._services["data_fetcher"].value

    def _create_data_fetcher(self):
        from data.fetcher import DataFetcher
        return DataFetcher()

    @property
    def data_storage(self):
        """Get data storage instance."""
        if "data_storage" in self._overrides:
            return self._overrides["data_storage"]
        return self._services["data_storage"].value

    def _create_data_storage(self):
        from data.storage import DataStorage
        return DataStorage()

    # =========================================================================
    # Strategy Services
    # =========================================================================

    @property
    def signal_generator(self):
        """Get signal generator instance."""
        if "signal_generator" in self._overrides:
            return self._overrides["signal_generator"]
        return self._services["signal_generator"].value

    def _create_signal_generator(self):
        from strategy.signals import SignalGenerator
        return SignalGenerator()

    @property
    def risk_manager(self):
        """Get risk manager instance."""
        if "risk_manager" in self._overrides:
            return self._overrides["risk_manager"]
        return self._services["risk_manager"].value

    def _create_risk_manager(self):
        from strategy.risk_manager import RiskManager
        return RiskManager()

    # =========================================================================
    # Execution Services
    # =========================================================================

    @property
    def broker(self):
        """Get broker instance."""
        if "broker" in self._overrides:
            return self._overrides["broker"]
        return self._services["broker"].value

    def _create_broker(self):
        from execution.broker import AlpacaBroker
        return AlpacaBroker(paper=True)

    # =========================================================================
    # Logging Services
    # =========================================================================

    @property
    def trade_logger(self):
        """Get trade logger instance."""
        if "trade_logger" in self._overrides:
            return self._overrides["trade_logger"]
        return self._services["trade_logger"].value

    def _create_trade_logger(self):
        from logging_system.trade_logger import TradeLogger
        return TradeLogger()

    @property
    def audit_trail(self):
        """Get audit trail instance."""
        if "audit_trail" in self._overrides:
            return self._overrides["audit_trail"]
        return self._services["audit_trail"].value

    def _create_audit_trail(self):
        from logging_system.audit_trail import AuditTrail
        return AuditTrail()

    # =========================================================================
    # Notification Services
    # =========================================================================

    @property
    def discord(self):
        """Get Discord notifier instance."""
        if "discord" in self._overrides:
            return self._overrides["discord"]
        return self._services["discord"].value

    def _create_discord(self):
        from notifications.discord import DiscordNotifier
        return DiscordNotifier()

    # =========================================================================
    # Service Management
    # =========================================================================

    def override(self, name: str, instance: Any) -> "Container":
        """
        Override a service with a custom instance.

        Useful for testing.

        Args:
            name: Service name
            instance: Custom instance

        Returns:
            Self for chaining
        """
        self._overrides[name] = instance
        return self

    def clear_overrides(self) -> None:
        """Clear all service overrides."""
        self._overrides.clear()

    def reset_service(self, name: str) -> None:
        """Reset a service to uninitialized state."""
        if name in self._services:
            self._services[name].reset()
        if name in self._overrides:
            del self._overrides[name]

    def reset_all(self) -> None:
        """Reset all services to uninitialized state."""
        for service in self._services.values():
            service.reset()
        self._overrides.clear()


# Convenience function for accessing container
def get_container() -> Container:
    """Get the singleton container instance."""
    return Container.instance()


# Context manager for testing with overrides
class ContainerScope:
    """
    Context manager for temporary container overrides.

    Usage:
        with ContainerScope(broker=mock_broker):
            # broker is mocked within this scope
            run_tests()
        # broker is restored after scope exits
    """

    def __init__(self, **overrides):
        self._overrides = overrides
        self._previous: Dict[str, Any] = {}

    def __enter__(self) -> Container:
        container = Container.instance()
        # Save previous overrides
        for key in self._overrides:
            if key in container._overrides:
                self._previous[key] = container._overrides[key]
        # Apply new overrides
        container._overrides.update(self._overrides)
        return container

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        container = Container.instance()
        # Restore previous overrides
        for key in self._overrides:
            if key in self._previous:
                container._overrides[key] = self._previous[key]
            elif key in container._overrides:
                del container._overrides[key]
        return False
