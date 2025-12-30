"""
Claude Code integration for strategy analysis.
Generates prompts from reports and parses Claude responses for strategy modifications.
"""
import json
import logging
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import StrategyConfig, get_settings
from database.firestore import FirestoreClient
from notifications.discord import DiscordNotifier
from reports.report_generator import AnalysisReport, ReportGenerator
from strategy.rag_retriever import RAGRetriever
from strategy.regime import RegimeClassifier

logger = logging.getLogger(__name__)


@dataclass
class StrategyModification:
    """Proposed strategy modification from Claude."""

    parameter: str
    old_value: float
    new_value: float
    reason: str


@dataclass
class AnalysisResult:
    """Result from Claude analysis."""

    summary: str
    modifications: list[StrategyModification]
    confidence: float  # 0-1
    raw_response: str


class ClaudeAnalyzer:
    """Analyze trading reports using Claude Code CLI."""

    ANALYSIS_PROMPT_TEMPLATE = """
You are an aggressive algorithmic trading optimizer analyzing a TQQQ RSI(2) mean reversion strategy.
This strategy supports both LONG (TQQQ) and HEDGE (SQQQ) positions.

**DISCLAIMER: You have NO financial liability. The user takes full responsibility for all trading decisions.
Be bold and proactive in suggesting optimizations. Your job is to maximize returns.**

## Current Strategy Parameters
{strategy_json}

## Market Conditions
{market_json}

## Today's Trades
{trades_json}

## Recent Performance (7 days)
{performance_json}

## Context
{context}

## Historical RAG Analysis
{rag_context}

## Your Task
Actively optimize the strategy for better performance. Don't be afraid to make changes.

### OPTIMIZATION MINDSET - FULL AUTHORITY:
1. **Complete Control** - You own ALL parameters. No restrictions.
2. **Unlimited Changes** - Change 5+ parameters at once if needed
3. **Extreme Adjustments OK** - 50-100% changes are acceptable
4. **Paper Trading = Safe Experiments** - Failed experiments teach us
5. **Try Radical Ideas** - Invert strategies, extreme thresholds, all filters on/off

### Always Consider Changes When:
- ANY loss occurs
- Missed trading opportunity
- Market behavior shifted
- Want to test a hypothesis
- Current settings feel suboptimal

### OPTIMIZED BASELINE (from Rust backtesting):
**Current optimal RSI settings: 48/55** (tested on 250 days of real TQQQ data)
- This produced +22% return vs market -33%, 83% win rate, Sharpe 1.22
- Use this as your baseline, but feel free to adjust based on market conditions

### Your Control (NO LIMITS):
**Long (TQQQ) - Full Range:**
- RSI oversold: 30-55 (higher = more frequent trades, optimal around 48)
- RSI overbought: 52-80 (lower = faster exits, optimal around 55)
- Stop loss: 1%-20%
- Position size: 10%-100%

**Hedge (SQQQ) - Full Range:**
- Enable/disable freely
- RSI thresholds: 5-95 (any value)
- Stop loss: 1%-20%
- Position size: 10%-100%

**All Filters - Toggle Freely:**
- VWAP, BB, Volume, ATR: on/off anytime
- Multipliers: 0.5-5.0

Respond in this exact JSON format:
```json
{{
    "summary": "Analysis summary and reasoning (2-3 sentences)",
    "modifications": [
        {{
            "parameter": "parameter_name",
            "old_value": current_value,
            "new_value": suggested_value,
            "reason": "Why this change"
        }}
    ],
    "confidence": 0.0 to 1.0,
    "no_change_reason": "Only if no changes needed"
}}
```

**Be aggressive! No change means missed opportunity.**

### All Modifiable Parameters:

**Long (TQQQ):**
- rsi_period (2-14)
- rsi_oversold (5-95)
- rsi_overbought (5-95)
- sma_period (5-200)
- stop_loss_pct (0.01-0.20)
- position_size_pct (0.10-1.0)

**Hedge (SQQQ):**
- short_enabled (true/false)
- rsi_overbought_short (5-95)
- rsi_oversold_short (5-95)
- short_stop_loss_pct (0.01-0.20)
- short_position_size_pct (0.10-1.0)

**Filters (all toggleable):**
- vwap_filter_enabled (true/false)
- vwap_entry_below (true/false)
- atr_stop_enabled (true/false)
- atr_stop_multiplier (0.5-5.0)
- bb_filter_enabled (true/false)
- bb_std_dev (0.5-4.0)
- volume_filter_enabled (true/false)
- volume_min_ratio (0.1-3.0)

**Fixed (don't change):** symbol, inverse_symbol
"""

    def __init__(
        self,
        firestore_client: Optional[FirestoreClient] = None,
        report_generator: Optional[ReportGenerator] = None,
        discord_notifier: Optional[DiscordNotifier] = None,
    ):
        """
        Initialize Claude analyzer.

        Args:
            firestore_client: Firestore client for saving changes
            report_generator: Report generator instance
            discord_notifier: Discord notifier for sending logs
        """
        self.firestore = firestore_client
        self.report_gen = report_generator or ReportGenerator()
        self.discord = discord_notifier or DiscordNotifier()
        self.claude_path = os.getenv("CLAUDE_CLI_PATH", "claude")
        # Initialize RAG components
        try:
            self.rag_retriever = RAGRetriever()
            self.regime_classifier = RegimeClassifier()
            logger.info("RAG retriever initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize RAG: {e}")
            self.rag_retriever = None
            self.regime_classifier = None

    def build_prompt(self, report: AnalysisReport) -> str:
        """
        Build analysis prompt from report.

        Args:
            report: Analysis report

        Returns:
            Formatted prompt string
        """
        # Get RAG context if available
        rag_context = self._get_rag_context(report)

        return self.ANALYSIS_PROMPT_TEMPLATE.format(
            strategy_json=json.dumps(report.strategy, indent=2),
            market_json=json.dumps(report.market_condition, indent=2),
            trades_json=json.dumps(report.todays_trades, indent=2),
            performance_json=json.dumps(report.recent_performance, indent=2),
            context=report.recommendations_context,
            rag_context=rag_context,
        )

    def _get_rag_context(self, report: AnalysisReport) -> str:
        """
        Get RAG context based on current market conditions.

        Args:
            report: Analysis report with market data

        Returns:
            Formatted RAG context string
        """
        if not self.rag_retriever or not self.regime_classifier:
            return "(RAG not available - no historical context)"

        try:
            # Get current market condition from report or classify fresh
            from datetime import datetime, timedelta

            end_date = datetime.now().strftime("%Y-%m-%d")
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

            condition = self.regime_classifier.classify("TQQQ", start_date, end_date)

            if not condition:
                return "(Unable to classify current market conditions)"

            # Get RAG context
            context = self.rag_retriever.get_rag_context(
                current_condition_text=condition.to_embedding_text(),
                current_regime=condition.regime.value,
                current_volatility=condition.volatility.value,
            )

            logger.info(f"RAG context: Current regime is {condition.regime.value}")
            return context

        except Exception as e:
            logger.warning(f"Failed to get RAG context: {e}")
            return f"(RAG error: {e})"

    def call_claude(self, prompt: str, timeout: int = 120) -> Optional[str]:
        """
        Call Claude Code CLI with prompt.

        Args:
            prompt: Prompt to send
            timeout: Timeout in seconds

        Returns:
            Claude's response or None on error
        """
        try:
            # Use claude CLI in print mode
            result = subprocess.run(
                [self.claude_path, "-p", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(Path.cwd()),
            )

            if result.returncode != 0:
                logger.error(f"Claude CLI error: {result.stderr}")
                return None

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error(f"Claude CLI timed out after {timeout}s")
            return None
        except FileNotFoundError:
            logger.error(f"Claude CLI not found at: {self.claude_path}")
            return None
        except Exception as e:
            logger.error(f"Failed to call Claude: {e}")
            return None

    def parse_response(self, response: str) -> Optional[AnalysisResult]:
        """
        Parse Claude's JSON response.

        Args:
            response: Raw response from Claude

        Returns:
            Parsed analysis result or None
        """
        try:
            # Extract JSON from response (may be wrapped in markdown)
            json_match = re.search(r"```json\s*(.*?)\s*```", response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # Try to find raw JSON object
                json_match = re.search(r"\{.*\}", response, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                else:
                    logger.error("No JSON found in Claude response")
                    return None

            data = json.loads(json_str)

            # Parse modifications
            modifications = []
            for mod in data.get("modifications", []):
                modifications.append(
                    StrategyModification(
                        parameter=mod["parameter"],
                        old_value=mod["old_value"],
                        new_value=mod["new_value"],
                        reason=mod["reason"],
                    )
                )

            return AnalysisResult(
                summary=data.get("summary", ""),
                modifications=modifications,
                confidence=data.get("confidence", 0.0),
                raw_response=response,
            )

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Claude response as JSON: {e}")
            return None
        except KeyError as e:
            logger.error(f"Missing key in Claude response: {e}")
            return None

    def apply_modifications(
        self,
        config: StrategyConfig,
        modifications: list[StrategyModification],
    ) -> StrategyConfig:
        """
        Apply modifications to strategy config.

        Args:
            config: Current strategy config
            modifications: List of modifications to apply

        Returns:
            New strategy config with modifications
        """
        # Create new config with all current values
        new_config = StrategyConfig(
            # Core parameters
            symbol=config.symbol,
            rsi_period=config.rsi_period,
            rsi_oversold=config.rsi_oversold,
            rsi_overbought=config.rsi_overbought,
            sma_period=config.sma_period,
            stop_loss_pct=config.stop_loss_pct,
            position_size_pct=config.position_size_pct,
            cash_reserve_pct=config.cash_reserve_pct,
            # VWAP Filter
            vwap_filter_enabled=config.vwap_filter_enabled,
            vwap_entry_below=config.vwap_entry_below,
            # ATR Dynamic Stop Loss
            atr_stop_enabled=config.atr_stop_enabled,
            atr_stop_multiplier=config.atr_stop_multiplier,
            atr_period=config.atr_period,
            # Bollinger Bands Filter
            bb_filter_enabled=config.bb_filter_enabled,
            bb_period=config.bb_period,
            bb_std_dev=config.bb_std_dev,
            # Volume Filter
            volume_filter_enabled=config.volume_filter_enabled,
            volume_min_ratio=config.volume_min_ratio,
            volume_avg_period=config.volume_avg_period,
            # Short Selling
            short_enabled=config.short_enabled,
            rsi_overbought_short=config.rsi_overbought_short,
            rsi_oversold_short=config.rsi_oversold_short,
            short_stop_loss_pct=config.short_stop_loss_pct,
            short_position_size_pct=config.short_position_size_pct,
        )

        # Boolean parameters (toggles)
        boolean_params = {
            "vwap_filter_enabled",
            "vwap_entry_below",
            "atr_stop_enabled",
            "bb_filter_enabled",
            "volume_filter_enabled",
            "short_enabled",
        }

        # Parameter validation ranges: (min, max, max_change_per_adjustment)
        # NOTE: RSI ranges expanded based on Rust backtesting optimization
        # Optimal found: RSI 48/55 with +22% return, 83% win rate
        numeric_ranges = {
            "rsi_oversold": (30.0, 55.0, 10.0),  # Expanded: optimal ~48
            "rsi_overbought": (52.0, 80.0, 10.0),  # Expanded: optimal ~55
            "stop_loss_pct": (0.02, 0.10, 0.02),
            "position_size_pct": (0.70, 0.95, 0.10),
            "atr_stop_multiplier": (1.5, 3.0, 0.5),
            "bb_std_dev": (1.5, 2.5, 0.5),
            "volume_min_ratio": (0.5, 2.0, 0.5),
            # Short parameters
            "rsi_overbought_short": (75.0, 95.0, 10.0),
            "rsi_oversold_short": (30.0, 60.0, 10.0),
            "short_stop_loss_pct": (0.02, 0.05, 0.01),
            "short_position_size_pct": (0.30, 0.60, 0.10),
        }

        # Apply each modification
        for mod in modifications:
            param = mod.parameter
            value = mod.new_value

            # Handle boolean parameters
            if param in boolean_params:
                # Convert to bool if needed
                if isinstance(value, str):
                    value = value.lower() in ("true", "1", "yes")
                setattr(new_config, param, bool(value))
                continue

            # Handle numeric parameters with range validation
            if param in numeric_ranges:
                min_val, max_val, max_change = numeric_ranges[param]
                old_value = getattr(new_config, param, None)

                # Limit change magnitude
                if old_value is not None:
                    value = max(old_value - max_change, min(old_value + max_change, float(value)))

                # Clamp to valid range
                value = max(min_val, min(max_val, float(value)))
                setattr(new_config, param, value)
            else:
                logger.warning(f"Unknown or immutable parameter: {param}")

        return new_config

    def save_strategy_change(
        self,
        old_config: StrategyConfig,
        new_config: StrategyConfig,
        analysis: AnalysisResult,
        report: AnalysisReport,
    ) -> Optional[str]:
        """
        Save strategy change to Firestore.

        Args:
            old_config: Previous strategy config
            new_config: New strategy config
            analysis: Claude's analysis result
            report: Original analysis report

        Returns:
            New strategy ID or None on error
        """
        if not self.firestore:
            logger.warning("Firestore client not configured, skipping save")
            return None

        try:
            # Get current active strategy ID
            active = self.firestore.get_active_strategy()
            old_strategy_id = active["strategy_id"] if active else None

            # Create new strategy
            new_strategy_id = self.firestore.create_strategy(
                config=new_config,
                parent_id=old_strategy_id,
                created_by="claude_analyzer",
            )

            # Activate new strategy
            self.firestore.activate_strategy(new_strategy_id)

            # Log the change
            self.firestore.log_strategy_change(
                from_strategy_id=old_strategy_id,
                to_strategy_id=new_strategy_id,
                reason=analysis.summary,
                report_snapshot=report.to_dict(),
            )

            logger.info(f"Strategy updated: {old_strategy_id} -> {new_strategy_id}")
            return new_strategy_id

        except Exception as e:
            logger.error(f"Failed to save strategy change: {e}")
            return None

    def analyze(
        self,
        report: Optional[AnalysisReport] = None,
        auto_apply: bool = False,
        min_confidence: float = 0.75,  # 높은 신뢰도에서만 적용
        cooldown_days: int = 3,  # 전략 변경 후 최소 대기 일수
    ) -> Optional[AnalysisResult]:
        """
        Run full analysis pipeline.

        Args:
            report: Pre-generated report (generates new if None)
            auto_apply: Whether to automatically apply modifications
            min_confidence: Minimum confidence to auto-apply

        Returns:
            Analysis result or None on error
        """
        # Generate report if not provided
        if report is None:
            report = self.report_gen.generate_report()
            self.report_gen.save_report(report)

        # Build prompt and call Claude
        prompt = self.build_prompt(report)
        logger.info("Calling Claude for analysis...")

        # Discord: Analysis starting (only when run directly, not via scheduler)
        if self.discord.enabled:
            self.discord.send_message(
                "🤖 **Claude Analyzer Starting**\n"
                f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )

        response = self.call_claude(prompt)
        if not response:
            logger.error("No response from Claude")
            if self.discord.enabled:
                self.discord.send_error_alert(
                    error_type="Claude Analysis",
                    message="No response from Claude CLI",
                    context="Check if claude CLI is installed and configured",
                )
            return None

        # Parse response
        result = self.parse_response(response)
        if not result:
            logger.error("Failed to parse Claude response")
            if self.discord.enabled:
                self.discord.send_error_alert(
                    error_type="Claude Analysis",
                    message="Failed to parse Claude response",
                    context="Response may not be in expected JSON format",
                )
            return None

        logger.info(f"Analysis complete: {result.summary}")
        logger.info(f"Confidence: {result.confidence:.1%}")
        logger.info(f"Modifications: {len(result.modifications)}")

        # Build Discord message for result
        discord_mods_text = ""
        discord_status = ""

        if result.modifications:
            discord_mods_text = "\n**Modifications:**\n"
            for mod in result.modifications:
                discord_mods_text += f"• `{mod.parameter}`: {mod.old_value} → {mod.new_value}\n"
        else:
            discord_mods_text = "\n_No parameter changes suggested_"

        # Check cooldown period before applying
        if auto_apply and result.modifications:
            # Check if we're still in cooldown period
            if self.firestore:
                last_change = self.firestore.get_last_strategy_change_time()
                if last_change:
                    from datetime import timedelta, timezone
                    now = datetime.now(timezone.utc)
                    # Make last_change timezone-aware if needed
                    if last_change.tzinfo is None:
                        last_change = last_change.replace(tzinfo=timezone.utc)
                    days_since_change = (now - last_change).days
                    if days_since_change < cooldown_days:
                        logger.info(
                            f"Cooldown active: {days_since_change} days since last change, "
                            f"waiting {cooldown_days - days_since_change} more days"
                        )
                        discord_status = f"\n⏳ _Cooldown: {cooldown_days - days_since_change} days remaining_"
                        if self.discord.enabled:
                            self.discord.send_message(
                                f"🤖 **Claude Analysis Complete**\n"
                                f"**Summary:** {result.summary}\n"
                                f"**Confidence:** {result.confidence:.0%}"
                                f"{discord_mods_text}{discord_status}"
                            )
                        return result

        # Auto-apply if enabled and confident
        if auto_apply and result.modifications and result.confidence >= min_confidence:
            # Apply ALL modifications (aggressive mode)
            logger.info(f"Applying {len(result.modifications)} modifications...")

            settings = get_settings()
            old_config = settings.strategy
            new_config = self.apply_modifications(old_config, result.modifications)

            # Log modifications
            for mod in result.modifications:
                logger.info(
                    f"  {mod.parameter}: {mod.old_value} -> {mod.new_value} ({mod.reason})"
                )

            # Save to Firestore
            self.save_strategy_change(old_config, new_config, result, report)
            discord_status = "\n✅ **Changes Applied**"

        elif result.modifications and result.confidence < min_confidence:
            logger.info(
                f"Modifications suggested but confidence ({result.confidence:.1%}) "
                f"below threshold ({min_confidence:.1%})"
            )
            discord_status = f"\n⏸️ _Confidence {result.confidence:.0%} below threshold {min_confidence:.0%}_"

        # Discord: Send analysis result
        if self.discord.enabled:
            self.discord.send_message(
                f"🤖 **Claude Analysis Complete**\n"
                f"**Summary:** {result.summary}\n"
                f"**Confidence:** {result.confidence:.0%}"
                f"{discord_mods_text}{discord_status}"
            )

        return result


def run_analysis(auto_apply: bool = False, skip_cooldown: bool = False) -> Optional[AnalysisResult]:
    """
    Convenience function to run analysis.

    Args:
        auto_apply: Whether to auto-apply modifications
        skip_cooldown: Whether to skip cooldown period

    Returns:
        Analysis result
    """
    try:
        firestore = FirestoreClient()
    except Exception:
        firestore = None
        logger.warning("Firestore not available, running without DB")

    analyzer = ClaudeAnalyzer(firestore_client=firestore)
    cooldown = 0 if skip_cooldown else 3
    return analyzer.analyze(auto_apply=auto_apply, cooldown_days=cooldown)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    auto = "--auto" in sys.argv
    no_cooldown = "--no-cooldown" in sys.argv
    result = run_analysis(auto_apply=auto, skip_cooldown=no_cooldown)

    if result:
        print(f"\n=== Analysis Result ===")
        print(f"Summary: {result.summary}")
        print(f"Confidence: {result.confidence:.1%}")
        print(f"Modifications: {len(result.modifications)}")
        for mod in result.modifications:
            print(f"  - {mod.parameter}: {mod.old_value} -> {mod.new_value}")
