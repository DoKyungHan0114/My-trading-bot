"""
Real-time data streaming via Alpaca WebSocket.
"""
import asyncio
import logging
from typing import Callable, Optional

try:
    from alpaca.data.live import StockDataStream
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False

from config.settings import get_settings

logger = logging.getLogger(__name__)


class DataStream:
    """Real-time market data stream using Alpaca WebSocket."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        secret_key: Optional[str] = None,
    ):
        """
        Initialize data stream.

        Args:
            api_key: Alpaca API key
            secret_key: Alpaca secret key
        """
        settings = get_settings()
        self.api_key = api_key or settings.alpaca.api_key
        self.secret_key = secret_key or settings.alpaca.secret_key
        self._stream: Optional[StockDataStream] = None
        self._callbacks: dict[str, list[Callable]] = {
            "bar": [],
            "trade": [],
            "quote": [],
        }
        self._running = False

    @property
    def stream(self) -> "StockDataStream":
        """Lazy initialize stream client."""
        if not ALPACA_AVAILABLE:
            raise ImportError("alpaca-py not installed")
        if self._stream is None:
            self._stream = StockDataStream(
                api_key=self.api_key,
                secret_key=self.secret_key,
            )
        return self._stream

    def on_bar(self, callback: Callable) -> None:
        """Register bar data callback."""
        self._callbacks["bar"].append(callback)

    def on_trade(self, callback: Callable) -> None:
        """Register trade data callback."""
        self._callbacks["trade"].append(callback)

    def on_quote(self, callback: Callable) -> None:
        """Register quote data callback."""
        self._callbacks["quote"].append(callback)

    async def _handle_bar(self, bar) -> None:
        """Handle incoming bar data."""
        for callback in self._callbacks["bar"]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(bar)
                else:
                    callback(bar)
            except Exception as e:
                logger.error(f"Error in bar callback: {e}")

    async def _handle_trade(self, trade) -> None:
        """Handle incoming trade data."""
        for callback in self._callbacks["trade"]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(trade)
                else:
                    callback(trade)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")

    async def _handle_quote(self, quote) -> None:
        """Handle incoming quote data."""
        for callback in self._callbacks["quote"]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(quote)
                else:
                    callback(quote)
            except Exception as e:
                logger.error(f"Error in quote callback: {e}")

    def subscribe_bars(self, symbols: list[str]) -> None:
        """Subscribe to bar data for symbols."""
        self.stream.subscribe_bars(self._handle_bar, *symbols)
        logger.info(f"Subscribed to bars: {symbols}")

    def subscribe_trades(self, symbols: list[str]) -> None:
        """Subscribe to trade data for symbols."""
        self.stream.subscribe_trades(self._handle_trade, *symbols)
        logger.info(f"Subscribed to trades: {symbols}")

    def subscribe_quotes(self, symbols: list[str]) -> None:
        """Subscribe to quote data for symbols."""
        self.stream.subscribe_quotes(self._handle_quote, *symbols)
        logger.info(f"Subscribed to quotes: {symbols}")

    async def start(self) -> None:
        """Start the data stream."""
        if self._running:
            logger.warning("Stream already running")
            return

        self._running = True
        logger.info("Starting data stream...")

        try:
            await self.stream._run_forever()
        except Exception as e:
            logger.error(f"Stream error: {e}")
            self._running = False
            raise

    def stop(self) -> None:
        """Stop the data stream."""
        if self._stream:
            self._stream.stop()
        self._running = False
        logger.info("Data stream stopped")

    @property
    def is_running(self) -> bool:
        """Check if stream is running."""
        return self._running
