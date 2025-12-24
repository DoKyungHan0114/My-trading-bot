"""
Discord Bot for TQQQ Trading System.
Responds to commands in Discord channel.
"""
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Optional

import discord
from discord import app_commands
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import get_settings
from database.firestore import FirestoreClient

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class TradingBot(discord.Client):
    """Discord bot for trading system status."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.firestore: Optional[FirestoreClient] = None
        self.settings = get_settings()

    async def setup_hook(self):
        """Setup slash commands."""
        await self.tree.sync()
        logger.info("Slash commands synced")

    async def on_ready(self):
        """Called when bot is ready."""
        logger.info(f"Logged in as {self.user}")
        try:
            self.firestore = FirestoreClient()
            logger.info("Firestore connected")
        except Exception as e:
            logger.warning(f"Firestore not available: {e}")


bot = TradingBot()


@bot.tree.command(name="status", description="Get trading bot status")
async def status(interaction: discord.Interaction):
    """Get current trading bot status."""
    await interaction.response.defer()

    try:
        # Get Alpaca account info
        from alpaca.trading.client import TradingClient

        trading_client = TradingClient(
            bot.settings.alpaca.api_key,
            bot.settings.alpaca.secret_key,
            paper=bot.settings.alpaca.is_paper,
        )
        account = trading_client.get_account()
        positions = trading_client.get_all_positions()

        # Format positions
        pos_text = ""
        if positions:
            for pos in positions:
                pnl = float(pos.unrealized_pl)
                pnl_pct = float(pos.unrealized_plpc) * 100
                emoji = "📈" if pnl >= 0 else "📉"
                pos_text += f"{emoji} **{pos.symbol}**: {pos.qty}주 @ ${float(pos.avg_entry_price):.2f}\n"
                pos_text += f"   현재가: ${float(pos.current_price):.2f} | P&L: ${pnl:+,.2f} ({pnl_pct:+.2f}%)\n"
        else:
            pos_text = "보유 포지션 없음"

        # Get active strategy from Firestore
        strategy_info = "N/A"
        if bot.firestore:
            try:
                strategy = bot.firestore.get_active_strategy()
                if strategy:
                    params = strategy.get("parameters", {})
                    strategy_info = (
                        f"RSI: {params.get('rsi_oversold', 30)}/{params.get('rsi_overbought', 75)} | "
                        f"SMA: {params.get('sma_period', 20)} | "
                        f"Stop: {params.get('stop_loss_pct', 0.05)*100:.1f}%"
                    )
            except Exception as e:
                logger.warning(f"Failed to get strategy: {e}")

        # Build embed
        equity = float(account.equity)
        buying_power = float(account.buying_power)
        daily_pnl = float(account.equity) - float(account.last_equity)
        daily_pnl_pct = (daily_pnl / float(account.last_equity)) * 100 if float(account.last_equity) > 0 else 0

        embed = discord.Embed(
            title="📊 TQQQ Trading Bot Status",
            color=discord.Color.green() if daily_pnl >= 0 else discord.Color.red(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name="💰 계좌",
            value=f"자산: **${equity:,.2f}**\n구매력: ${buying_power:,.2f}",
            inline=True,
        )
        embed.add_field(
            name="📈 오늘 수익",
            value=f"**${daily_pnl:+,.2f}** ({daily_pnl_pct:+.2f}%)",
            inline=True,
        )
        embed.add_field(
            name="⚙️ 전략",
            value=strategy_info,
            inline=False,
        )
        embed.add_field(
            name="📦 포지션",
            value=pos_text,
            inline=False,
        )
        embed.set_footer(text="Paper Trading" if bot.settings.alpaca.is_paper else "Live Trading")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        logger.error(f"Status command error: {e}")
        await interaction.followup.send(f"❌ 오류 발생: {str(e)}")


@bot.tree.command(name="positions", description="Get current positions")
async def positions(interaction: discord.Interaction):
    """Get current positions detail."""
    await interaction.response.defer()

    try:
        from alpaca.trading.client import TradingClient

        trading_client = TradingClient(
            bot.settings.alpaca.api_key,
            bot.settings.alpaca.secret_key,
            paper=bot.settings.alpaca.is_paper,
        )
        positions = trading_client.get_all_positions()

        if not positions:
            await interaction.followup.send("📭 보유 포지션이 없습니다.")
            return

        embed = discord.Embed(
            title="📦 현재 포지션",
            color=discord.Color.blue(),
            timestamp=datetime.utcnow(),
        )

        total_value = 0
        total_pnl = 0

        for pos in positions:
            market_value = float(pos.market_value)
            pnl = float(pos.unrealized_pl)
            pnl_pct = float(pos.unrealized_plpc) * 100
            total_value += market_value
            total_pnl += pnl

            emoji = "📈" if pnl >= 0 else "📉"
            embed.add_field(
                name=f"{emoji} {pos.symbol}",
                value=(
                    f"수량: **{pos.qty}주**\n"
                    f"평균단가: ${float(pos.avg_entry_price):.2f}\n"
                    f"현재가: ${float(pos.current_price):.2f}\n"
                    f"평가금액: ${market_value:,.2f}\n"
                    f"P&L: **${pnl:+,.2f}** ({pnl_pct:+.2f}%)"
                ),
                inline=True,
            )

        embed.add_field(
            name="📊 총계",
            value=f"평가금액: ${total_value:,.2f}\n총 P&L: **${total_pnl:+,.2f}**",
            inline=False,
        )

        await interaction.followup.send(embed=embed)

    except Exception as e:
        logger.error(f"Positions command error: {e}")
        await interaction.followup.send(f"❌ 오류 발생: {str(e)}")


@bot.tree.command(name="strategy", description="Get current strategy parameters")
async def strategy(interaction: discord.Interaction):
    """Get current strategy info."""
    await interaction.response.defer()

    try:
        if not bot.firestore:
            await interaction.followup.send("❌ Firestore 연결 안됨")
            return

        strategy = bot.firestore.get_active_strategy()
        if not strategy:
            await interaction.followup.send("❌ 활성화된 전략이 없습니다.")
            return

        params = strategy.get("parameters", {})

        embed = discord.Embed(
            title="⚙️ 현재 전략",
            color=discord.Color.purple(),
            timestamp=datetime.utcnow(),
        )
        embed.add_field(
            name="📊 RSI 설정",
            value=(
                f"Period: {params.get('rsi_period', 2)}\n"
                f"Oversold: {params.get('rsi_oversold', 30)}\n"
                f"Overbought: {params.get('rsi_overbought', 75)}"
            ),
            inline=True,
        )
        embed.add_field(
            name="📈 이동평균",
            value=f"SMA Period: {params.get('sma_period', 20)}",
            inline=True,
        )
        embed.add_field(
            name="🛡️ 리스크 관리",
            value=(
                f"Stop Loss: {params.get('stop_loss_pct', 0.05)*100:.1f}%\n"
                f"Position Size: {params.get('position_size_pct', 0.9)*100:.0f}%\n"
                f"Cash Reserve: {params.get('cash_reserve_pct', 0.1)*100:.0f}%"
            ),
            inline=True,
        )

        # Filters
        filters = []
        if params.get("vwap_filter_enabled"):
            filters.append("✅ VWAP Filter")
        if params.get("atr_stop_enabled"):
            filters.append(f"✅ ATR Stop (x{params.get('atr_stop_multiplier', 2)})")
        if params.get("bb_filter_enabled"):
            filters.append("✅ Bollinger Bands")
        if params.get("volume_filter_enabled"):
            filters.append("✅ Volume Filter")

        embed.add_field(
            name="🔧 활성 필터",
            value="\n".join(filters) if filters else "기본 설정",
            inline=False,
        )

        # Hedge settings
        if params.get("short_enabled"):
            embed.add_field(
                name="🔄 헷지 (SQQQ)",
                value=(
                    f"Symbol: {params.get('inverse_symbol', 'SQQQ')}\n"
                    f"RSI Overbought: {params.get('rsi_overbought_short', 90)}\n"
                    f"Position Size: {params.get('short_position_size_pct', 0.3)*100:.0f}%"
                ),
                inline=True,
            )

        strategy_id = strategy.get("strategy_id", "N/A")
        embed.set_footer(text=f"Strategy ID: {strategy_id[:8]}...")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        logger.error(f"Strategy command error: {e}")
        await interaction.followup.send(f"❌ 오류 발생: {str(e)}")


@bot.tree.command(name="help", description="Show available commands")
async def help_cmd(interaction: discord.Interaction):
    """Show help message."""
    embed = discord.Embed(
        title="📖 TQQQ Trading Bot 명령어",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="/status",
        value="봇 상태, 계좌 정보, 오늘 수익 확인",
        inline=False,
    )
    embed.add_field(
        name="/positions",
        value="현재 보유 포지션 상세 정보",
        inline=False,
    )
    embed.add_field(
        name="/strategy",
        value="현재 적용된 전략 파라미터 확인",
        inline=False,
    )
    embed.add_field(
        name="/help",
        value="이 도움말 표시",
        inline=False,
    )

    await interaction.response.send_message(embed=embed)


def main():
    """Run the Discord bot."""
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.error("DISCORD_BOT_TOKEN not set")
        sys.exit(1)

    logger.info("Starting Discord bot...")
    bot.run(token)


if __name__ == "__main__":
    main()
