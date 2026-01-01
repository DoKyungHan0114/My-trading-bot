#!/usr/bin/env python3
"""
TQQQ RSI(2) Mean Reversion Trading System - Live/Paper Trading.

Usage:
    python trading_bot.py --mode paper   # Paper trading
    python trading_bot.py --mode live    # Live trading (caution!)
"""
import argparse
import asyncio
import logging
import signal
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from config.settings import get_settings, configure_for_mode, StrategyConfig
from config.constants import TradingMode, SYMBOL, INVERSE_SYMBOL
from data.fetcher import DataFetcher
from strategy.signals import SignalGenerator
from strategy.risk_manager import RiskManager
from execution.broker import AlpacaBroker
from execution.portfolio import Portfolio
from execution.orders import Order
from logging_system.trade_logger import TradeLogger
from logging_system.audit_trail import AuditTrail, AuditEventType
from notifications.discord import DiscordNotifier

# Try to import Firestore for dynamic strategy loading
try:
    from database.firestore import FirestoreClient
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False

# Strategy reload interval (seconds)
STRATEGY_RELOAD_INTERVAL = 300  # 5 minutes

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(Path(__file__).parent / "logs" / "trading.log"),
    ],
)
logger = logging.getLogger(__name__)


class TradingBot:
    """Main trading bot orchestrator."""

    def __init__(self, mode: str = "paper"):
        """
        Initialize trading bot.

        Args:
            mode: Trading mode (paper or live)
        """
        self.mode = TradingMode(mode)
        self.settings = configure_for_mode(mode)

        # Initialize components
        self.data_fetcher = DataFetcher()
        self.signal_generator = SignalGenerator()
        self.risk_manager = RiskManager()
        self.broker = AlpacaBroker(paper=(self.mode != TradingMode.LIVE))
        self.trade_logger = TradeLogger()
        self.audit_trail = AuditTrail()
        self.discord = DiscordNotifier()

        # Initialize Firestore for dynamic strategy loading
        self.firestore: Optional[FirestoreClient] = None
        self.current_strategy_id: Optional[str] = None
        self.last_strategy_check: Optional[datetime] = None

        if FIRESTORE_AVAILABLE:
            try:
                self.firestore = FirestoreClient()
                logger.info("Firestore connected - dynamic strategy reload enabled")
            except Exception as e:
                logger.warning(f"Firestore not available: {e}")
                self.firestore = None

        # State - Long (TQQQ)
        self.running = False
        self.entry_price: Optional[float] = None
        self.entry_date: Optional[datetime] = None
        self.entry_signal = None  # Store signal for trade review

        # State - Hedge (SQQQ)
        self.hedge_entry_price: Optional[float] = None
        self.hedge_entry_date: Optional[datetime] = None
        self.hedge_entry_signal = None  # Store signal for trade review

        # Signal handlers
        signal.signal(signal.SIGINT, self._handle_shutdown)
        signal.signal(signal.SIGTERM, self._handle_shutdown)

    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received...")
        self.running = False

    def start(self):
        """Start the trading bot."""
        logger.info("=" * 60)
        logger.info(f"Starting TQQQ Trading Bot - Mode: {self.mode.value.upper()}")
        logger.info("=" * 60)

        # Validate API credentials
        if not self.settings.alpaca.validate():
            logger.error("Alpaca API credentials not configured!")
            logger.error("Please set ALPACA_API_KEY and ALPACA_SECRET_KEY in .env")
            return

        # Log system start
        self.audit_trail.log(
            AuditEventType.SYSTEM_START,
            f"Trading bot started in {self.mode.value} mode",
            {"mode": self.mode.value},
        )

        # Get account info
        account = self.broker.get_account()
        logger.info(f"Account: {account['account_number']}")
        logger.info(f"Equity: ${account['equity']:,.2f}")
        logger.info(f"Buying Power: ${account['buying_power']:,.2f}")

        # Load initial strategy from Firestore
        self._load_initial_strategy()

        # Send startup notification
        if self.discord.enabled:
            strategy = self.settings.strategy
            self.discord.send_message(
                f"🚀 **TQQQ Trading Bot Started**\n"
                f"Mode: {self.mode.value.upper()}\n"
                f"Equity: ${account['equity']:,.2f}\n"
                f"Strategy: RSI({strategy.rsi_period}) "
                f"[{strategy.rsi_oversold}/{strategy.rsi_overbought}] "
                f"SMA{strategy.sma_period}"
            )

        self.running = True
        self._run_trading_loop()

    def _run_trading_loop(self):
        """Main trading loop."""
        logger.info("Entering trading loop...")

        while self.running:
            try:
                # Check if market is open
                if not self.broker.is_market_open():
                    logger.debug("Market is closed, waiting...")
                    time.sleep(60)
                    continue

                # Check for strategy updates from Firestore
                self._check_strategy_update()

                # Run trading logic
                self._check_signals()

                # Wait for next check (every minute)
                time.sleep(60)

            except Exception as e:
                logger.exception(f"Error in trading loop: {e}")
                self.audit_trail.log_error(e, "trading_loop")

                if self.discord.enabled:
                    self.discord.send_error_alert(
                        error_type=type(e).__name__,
                        message=str(e),
                        context="Trading loop error",
                    )

                # Wait before retrying
                time.sleep(30)

        self._shutdown()

    def _check_signals(self):
        """Check for trading signals and execute trades."""
        settings = self.settings
        strategy = settings.strategy

        # Get current positions
        long_position = self.broker.get_position(SYMBOL)
        hedge_position = self.broker.get_position(INVERSE_SYMBOL) if strategy.short_enabled else None

        has_long = long_position is not None
        has_hedge = hedge_position is not None

        # Fetch recent data (need enough for SMA calculation)
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d")

        df = self.data_fetcher.get_daily_bars(SYMBOL, start_date, end_date)

        if len(df) < strategy.sma_period:
            logger.warning("Insufficient data for analysis")
            return

        # Prepare data with indicators
        df = self.signal_generator.prepare_data(df)

        # === LONG POSITION (TQQQ) ===
        if has_long:
            signal = self.signal_generator.generate_exit_signal(
                df,
                entry_price=self.entry_price or long_position["avg_entry_price"],
                stop_loss_pct=strategy.stop_loss_pct,
            )
            if signal:
                self._execute_sell(long_position, signal)
        else:
            signal = self.signal_generator.generate_entry_signal(df, has_position=False)
            if signal:
                if self.discord.enabled:
                    self.discord.send_signal(
                        signal_type=signal.signal_type.value,
                        symbol=signal.symbol,
                        price=signal.price,
                        rsi=signal.rsi,
                        reason=signal.reason,
                    )
                self._execute_buy(signal)

        # === HEDGE POSITION (SQQQ) ===
        if strategy.short_enabled:
            # Fetch SQQQ data for hedge signals
            hedge_df = self.data_fetcher.get_daily_bars(INVERSE_SYMBOL, start_date, end_date)
            if len(hedge_df) > 0:
                current_hedge_price = float(hedge_df.iloc[-1]["close"])

                if has_hedge:
                    # Check hedge exit
                    signal = self.signal_generator.generate_short_exit_signal(
                        df,
                        entry_price=self.entry_price or 0,
                        stop_loss_pct=strategy.short_stop_loss_pct,
                        is_hedge=True,
                        hedge_entry_price=self.hedge_entry_price or hedge_position["avg_entry_price"],
                        current_hedge_price=current_hedge_price,
                    )
                    if signal:
                        self._execute_hedge_sell(hedge_position, signal)
                else:
                    # Check hedge entry (only if no long position - don't hedge and long at same time)
                    if not has_long:
                        signal = self.signal_generator.generate_short_entry_signal(df)
                        if signal:
                            if self.discord.enabled:
                                self.discord.send_signal(
                                    signal_type="HEDGE_BUY",
                                    symbol=INVERSE_SYMBOL,
                                    price=current_hedge_price,
                                    rsi=signal.rsi,
                                    reason=signal.reason,
                                )
                            self._execute_hedge_buy(current_hedge_price, signal)

    def _execute_buy(self, signal):
        """Execute buy order."""
        from strategy.signals import Signal
        current_price = signal.price
        reason = signal.reason

        account = self.broker.get_account()

        # Calculate position size
        pos_size = self.risk_manager.calculate_position_size(
            account_value=account["equity"],
            current_price=current_price,
            use_fractional=True,
        )

        if pos_size.shares <= 0:
            logger.warning("Position size too small")
            return

        # Create and submit order
        order = Order.market_buy(
            symbol=SYMBOL,
            quantity=pos_size.shares,
            signal_reason=reason,
        )

        filled_order = self.broker.submit_order(order)

        if filled_order.is_filled:
            self.entry_price = filled_order.fill_price
            self.entry_date = filled_order.filled_at
            self.entry_signal = signal  # Store for exit trade logging

            # Log trade with indicator values
            self.trade_logger.log_trade(
                symbol=SYMBOL,
                side="BUY",
                quantity=filled_order.filled_quantity,
                price=current_price,
                fill_price=filled_order.fill_price,
                order_type=filled_order.order_type.value,
                signal_reason=reason,
                order_id_alpaca=filled_order.alpaca_order_id,
                rsi_value=signal.rsi,
                vwap_value=signal.vwap,
                sma_value=signal.sma,
                day_high=signal.day_high,
                day_low=signal.day_low,
            )

            # Audit
            self.audit_trail.log_order(
                AuditEventType.ORDER_FILLED,
                order_id=filled_order.order_id,
                symbol=SYMBOL,
                side="BUY",
                quantity=filled_order.filled_quantity,
                price=filled_order.fill_price,
            )

            # Discord notification
            if self.discord.enabled:
                self.discord.send_trade_notification(
                    symbol=SYMBOL,
                    side="BUY",
                    quantity=filled_order.filled_quantity,
                    price=filled_order.fill_price,
                    reason=reason,
                )

            logger.info(
                f"BUY executed: {filled_order.filled_quantity:.4f} {SYMBOL} "
                f"@ ${filled_order.fill_price:.2f}"
            )

    def _execute_sell(self, position: dict, signal):
        """Execute sell order."""
        reason = signal.reason
        quantity = position["quantity"]
        entry_price = self.entry_price or position["avg_entry_price"]

        # Create and submit order
        order = Order.market_sell(
            symbol=SYMBOL,
            quantity=quantity,
            signal_reason=reason,
        )

        filled_order = self.broker.submit_order(order)

        if filled_order.is_filled:
            # Calculate P&L
            pnl = (filled_order.fill_price - entry_price) * quantity
            pnl_pct = (pnl / (entry_price * quantity)) * 100

            holding_days = 0
            holding_minutes = None
            if self.entry_date:
                holding_delta = datetime.utcnow() - self.entry_date
                holding_days = holding_delta.days
                holding_minutes = int(holding_delta.total_seconds() / 60)

            # Get entry info for trade review
            entry_time_str = self.entry_date.isoformat() if self.entry_date else None

            # Log trade with indicator values
            self.trade_logger.log_trade(
                symbol=SYMBOL,
                side="SELL",
                quantity=filled_order.filled_quantity,
                price=filled_order.fill_price,
                fill_price=filled_order.fill_price,
                order_type=filled_order.order_type.value,
                signal_reason=reason,
                order_id_alpaca=filled_order.alpaca_order_id,
                realized_pnl_usd=pnl,
                holding_period_days=holding_days,
                rsi_value=signal.rsi,
                vwap_value=signal.vwap,
                sma_value=signal.sma,
                day_high=signal.day_high,
                day_low=signal.day_low,
                holding_minutes=holding_minutes,
                entry_price=entry_price,
                entry_time=entry_time_str,
            )

            # Audit
            self.audit_trail.log_order(
                AuditEventType.ORDER_FILLED,
                order_id=filled_order.order_id,
                symbol=SYMBOL,
                side="SELL",
                quantity=filled_order.filled_quantity,
                price=filled_order.fill_price,
                pnl=pnl,
            )

            # Discord notification
            if self.discord.enabled:
                self.discord.send_trade_notification(
                    symbol=SYMBOL,
                    side="SELL",
                    quantity=filled_order.filled_quantity,
                    price=filled_order.fill_price,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    reason=reason,
                )

            logger.info(
                f"SELL executed: {filled_order.filled_quantity:.4f} {SYMBOL} "
                f"@ ${filled_order.fill_price:.2f}, P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)"
            )

            # Reset state
            self.entry_price = None
            self.entry_date = None
            self.entry_signal = None

    def _execute_hedge_buy(self, current_price: float, signal):
        """Execute hedge buy order (SQQQ long)."""
        reason = signal.reason
        account = self.broker.get_account()
        strategy = self.settings.strategy

        # Calculate hedge position size
        pos_size = self.risk_manager.calculate_position_size(
            account_value=account["equity"],
            current_price=current_price,
            use_fractional=True,
            position_size_pct=strategy.short_position_size_pct,
        )

        if pos_size.shares <= 0:
            logger.warning("Hedge position size too small")
            return

        # Create and submit order
        order = Order.market_buy(
            symbol=INVERSE_SYMBOL,
            quantity=pos_size.shares,
            signal_reason=reason,
        )

        filled_order = self.broker.submit_order(order)

        if filled_order.is_filled:
            self.hedge_entry_price = filled_order.fill_price
            self.hedge_entry_date = filled_order.filled_at
            self.hedge_entry_signal = signal

            # Log trade with indicator values
            self.trade_logger.log_trade(
                symbol=INVERSE_SYMBOL,
                side="HEDGE_BUY",
                quantity=filled_order.filled_quantity,
                price=current_price,
                fill_price=filled_order.fill_price,
                order_type=filled_order.order_type.value,
                signal_reason=reason,
                order_id_alpaca=filled_order.alpaca_order_id,
                rsi_value=signal.rsi,
                vwap_value=signal.vwap,
                sma_value=signal.sma,
                day_high=signal.day_high,
                day_low=signal.day_low,
            )

            # Audit
            self.audit_trail.log_order(
                AuditEventType.ORDER_FILLED,
                order_id=filled_order.order_id,
                symbol=INVERSE_SYMBOL,
                side="HEDGE_BUY",
                quantity=filled_order.filled_quantity,
                price=filled_order.fill_price,
            )

            # Discord notification
            if self.discord.enabled:
                self.discord.send_trade_notification(
                    symbol=INVERSE_SYMBOL,
                    side="HEDGE_BUY",
                    quantity=filled_order.filled_quantity,
                    price=filled_order.fill_price,
                    reason=reason,
                )

            logger.info(
                f"HEDGE_BUY executed: {filled_order.filled_quantity:.4f} {INVERSE_SYMBOL} "
                f"@ ${filled_order.fill_price:.2f}"
            )

    def _execute_hedge_sell(self, position: dict, signal):
        """Execute hedge sell order (SQQQ close)."""
        reason = signal.reason
        quantity = position["quantity"]
        entry_price = self.hedge_entry_price or position["avg_entry_price"]

        # Create and submit order
        order = Order.market_sell(
            symbol=INVERSE_SYMBOL,
            quantity=quantity,
            signal_reason=reason,
        )

        filled_order = self.broker.submit_order(order)

        if filled_order.is_filled:
            # Calculate P&L
            pnl = (filled_order.fill_price - entry_price) * quantity
            pnl_pct = (pnl / (entry_price * quantity)) * 100

            holding_days = 0
            holding_minutes = None
            if self.hedge_entry_date:
                holding_delta = datetime.utcnow() - self.hedge_entry_date
                holding_days = holding_delta.days
                holding_minutes = int(holding_delta.total_seconds() / 60)

            entry_time_str = self.hedge_entry_date.isoformat() if self.hedge_entry_date else None

            # Log trade with indicator values
            self.trade_logger.log_trade(
                symbol=INVERSE_SYMBOL,
                side="HEDGE_SELL",
                quantity=filled_order.filled_quantity,
                price=filled_order.fill_price,
                fill_price=filled_order.fill_price,
                order_type=filled_order.order_type.value,
                signal_reason=reason,
                order_id_alpaca=filled_order.alpaca_order_id,
                realized_pnl_usd=pnl,
                holding_period_days=holding_days,
                rsi_value=signal.rsi,
                vwap_value=signal.vwap,
                sma_value=signal.sma,
                day_high=signal.day_high,
                day_low=signal.day_low,
                holding_minutes=holding_minutes,
                entry_price=entry_price,
                entry_time=entry_time_str,
            )

            # Audit
            self.audit_trail.log_order(
                AuditEventType.ORDER_FILLED,
                order_id=filled_order.order_id,
                symbol=INVERSE_SYMBOL,
                side="HEDGE_SELL",
                quantity=filled_order.filled_quantity,
                price=filled_order.fill_price,
                pnl=pnl,
            )

            # Discord notification
            if self.discord.enabled:
                self.discord.send_trade_notification(
                    symbol=INVERSE_SYMBOL,
                    side="HEDGE_SELL",
                    quantity=filled_order.filled_quantity,
                    price=filled_order.fill_price,
                    pnl=pnl,
                    pnl_pct=pnl_pct,
                    reason=reason,
                )

            logger.info(
                f"HEDGE_SELL executed: {filled_order.filled_quantity:.4f} {INVERSE_SYMBOL} "
                f"@ ${filled_order.fill_price:.2f}, P&L: ${pnl:+.2f} ({pnl_pct:+.2f}%)"
            )

            # Reset hedge state
            self.hedge_entry_price = None
            self.hedge_entry_date = None
            self.hedge_entry_signal = None

    def _load_initial_strategy(self):
        """Load initial strategy from Firestore if available."""
        if not self.firestore:
            logger.info("Using local strategy config (Firestore not available)")
            return

        try:
            active_strategy = self.firestore.get_active_strategy()
            if active_strategy:
                self.current_strategy_id = active_strategy.get("strategy_id")
                new_config = self.firestore.strategy_to_config(active_strategy)
                self._apply_strategy(new_config, "initial load")
                logger.info(f"Loaded strategy from Firestore: {self.current_strategy_id}")
            else:
                logger.info("No active strategy in Firestore, using local config")
        except Exception as e:
            logger.warning(f"Failed to load strategy from Firestore: {e}")

    def _check_strategy_update(self):
        """Check for strategy updates from Firestore periodically."""
        if not self.firestore:
            return

        now = datetime.now()

        # Check every STRATEGY_RELOAD_INTERVAL seconds
        if self.last_strategy_check:
            elapsed = (now - self.last_strategy_check).total_seconds()
            if elapsed < STRATEGY_RELOAD_INTERVAL:
                return

        self.last_strategy_check = now

        try:
            active_strategy = self.firestore.get_active_strategy()
            if not active_strategy:
                return

            new_strategy_id = active_strategy.get("strategy_id")

            # Check if strategy has changed
            if new_strategy_id and new_strategy_id != self.current_strategy_id:
                old_id = self.current_strategy_id
                self.current_strategy_id = new_strategy_id
                new_config = self.firestore.strategy_to_config(active_strategy)
                self._apply_strategy(new_config, "Firestore update")

                # Log the change
                logger.info(f"Strategy updated: {old_id} -> {new_strategy_id}")
                self.audit_trail.log(
                    AuditEventType.CONFIG_CHANGE,
                    f"Strategy reloaded from Firestore",
                    {
                        "old_strategy_id": old_id,
                        "new_strategy_id": new_strategy_id,
                        "rsi_oversold": new_config.rsi_oversold,
                        "rsi_overbought": new_config.rsi_overbought,
                        "sma_period": new_config.sma_period,
                        "stop_loss_pct": new_config.stop_loss_pct,
                    },
                )

                # Discord notification
                if self.discord.enabled:
                    self.discord.send_message(
                        f"🔄 **Strategy Updated**\n"
                        f"RSI: [{new_config.rsi_oversold}/{new_config.rsi_overbought}]\n"
                        f"SMA: {new_config.sma_period}\n"
                        f"Stop Loss: {new_config.stop_loss_pct:.1%}"
                    )

        except Exception as e:
            logger.warning(f"Failed to check strategy update: {e}")

    def _apply_strategy(self, new_config: StrategyConfig, source: str):
        """Apply new strategy configuration."""
        old = self.settings.strategy
        self.settings.strategy = new_config

        # Update signal generator with new parameters
        self.signal_generator = SignalGenerator()

        logger.info(
            f"Strategy applied ({source}): "
            f"RSI[{old.rsi_oversold}->{new_config.rsi_oversold}, "
            f"{old.rsi_overbought}->{new_config.rsi_overbought}] "
            f"SMA[{old.sma_period}->{new_config.sma_period}] "
            f"StopLoss[{old.stop_loss_pct:.1%}->{new_config.stop_loss_pct:.1%}]"
        )

    def _shutdown(self):
        """Shutdown the bot gracefully."""
        logger.info("Shutting down trading bot...")

        self.audit_trail.log(
            AuditEventType.SYSTEM_STOP,
            "Trading bot stopped",
        )

        if self.discord.enabled:
            self.discord.send_message("🛑 **TQQQ Trading Bot Stopped**")

        logger.info("Shutdown complete")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="TQQQ RSI(2) Mean Reversion Trading Bot"
    )

    parser.add_argument(
        "--mode",
        type=str,
        choices=["paper", "live"],
        default="paper",
        help="Trading mode (paper or live)",
    )

    args = parser.parse_args()

    if args.mode == "live":
        logger.warning("=" * 60)
        logger.warning("WARNING: LIVE TRADING MODE")
        logger.warning("Real money will be used!")
        logger.warning("=" * 60)

        confirm = input("Type 'CONFIRM' to proceed with live trading: ")
        if confirm != "CONFIRM":
            logger.info("Live trading cancelled")
            return

    bot = TradingBot(mode=args.mode)
    bot.start()


if __name__ == "__main__":
    main()
