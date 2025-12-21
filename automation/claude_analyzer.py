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
from reports.report_generator import AnalysisReport, ReportGenerator

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
You are analyzing a TQQQ RSI(2) mean reversion trading strategy.

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

## Your Task
Analyze the current strategy performance and decide IF modifications are needed.

### CRITICAL RULES - 안정성 우선:
1. **변경하지 않는 것이 기본값** - 충분한 근거 없이 파라미터를 바꾸지 마세요
2. **단기 손실에 과민 반응 금지** - 1-2일 손실은 정상적인 변동입니다
3. **한 번에 1개 파라미터만** - 여러 개를 동시에 바꾸면 원인 파악 불가
4. **작은 폭으로만 조정** - 한 번에 최대 10-15% 범위 내 변경

### 변경이 필요한 경우 (다음 조건 중 하나 이상 해당시에만):
- 연속 3일 이상 손실
- 7일 누적 손실률 > -10%
- 승률이 30% 미만
- Stop loss 연속 2회 이상 발동

### 변경하지 말아야 하는 경우:
- 7일 누적 수익 중 (현재 전략 유지)
- 1-2일 단기 손실 (노이즈일 가능성)
- 최근 전략 변경 후 3일 미경과 (평가 기간 필요)
- 시장 변동성이 일시적으로 높은 경우

### 수정 가이드 (필요한 경우에만):
- Stop loss 연속 발동 → stop_loss_pct +0.01~0.02
- 진입 기회 부족 → rsi_oversold +3~5
- 청산이 너무 늦음 → rsi_overbought -3~5
- 변동성 과다 → position_size_pct -0.05~0.10

Respond in this exact JSON format:
```json
{{
    "summary": "Brief analysis summary (2-3 sentences)",
    "modifications": [
        {{
            "parameter": "parameter_name",
            "old_value": current_value,
            "new_value": suggested_value,
            "reason": "Specific reason for change"
        }}
    ],
    "confidence": 0.0 to 1.0,
    "no_change_reason": "If no modifications, explain why current settings are appropriate"
}}
```

**IMPORTANT: modifications 배열이 비어있어도 됩니다. 불필요한 변경은 손실을 초래합니다.**

Valid parameters to modify:
- rsi_oversold (current: 30.0, range: 25-35) - 작은 범위 내 조정
- rsi_overbought (current: 75.0, range: 70-80) - 작은 범위 내 조정
- stop_loss_pct (current: 0.05, range: 0.04-0.08) - 보수적 범위
- position_size_pct (current: 0.90, range: 0.70-0.95)

DO NOT modify: rsi_period (must stay 2), symbol
"""

    def __init__(
        self,
        firestore_client: Optional[FirestoreClient] = None,
        report_generator: Optional[ReportGenerator] = None,
    ):
        """
        Initialize Claude analyzer.

        Args:
            firestore_client: Firestore client for saving changes
            report_generator: Report generator instance
        """
        self.firestore = firestore_client
        self.report_gen = report_generator or ReportGenerator()
        self.claude_path = os.getenv("CLAUDE_CLI_PATH", "claude")

    def build_prompt(self, report: AnalysisReport) -> str:
        """
        Build analysis prompt from report.

        Args:
            report: Analysis report

        Returns:
            Formatted prompt string
        """
        return self.ANALYSIS_PROMPT_TEMPLATE.format(
            strategy_json=json.dumps(report.strategy, indent=2),
            market_json=json.dumps(report.market_condition, indent=2),
            trades_json=json.dumps(report.todays_trades, indent=2),
            performance_json=json.dumps(report.recent_performance, indent=2),
            context=report.recommendations_context,
        )

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
        # Create new config with current values
        new_config = StrategyConfig(
            symbol=config.symbol,
            rsi_period=config.rsi_period,
            rsi_oversold=config.rsi_oversold,
            rsi_overbought=config.rsi_overbought,
            sma_period=config.sma_period,
            stop_loss_pct=config.stop_loss_pct,
            position_size_pct=config.position_size_pct,
            cash_reserve_pct=config.cash_reserve_pct,
        )

        # Apply each modification
        for mod in modifications:
            param = mod.parameter
            value = mod.new_value
            old_value = getattr(new_config, param, None)

            # Validate and apply (conservative ranges to prevent oscillation)
            if param == "rsi_oversold":
                # Limit change to max 5 points per adjustment
                if old_value is not None:
                    value = max(old_value - 5, min(old_value + 5, value))
                new_config.rsi_oversold = max(25.0, min(35.0, value))
            elif param == "rsi_overbought":
                # Limit change to max 5 points per adjustment
                if old_value is not None:
                    value = max(old_value - 5, min(old_value + 5, value))
                new_config.rsi_overbought = max(70.0, min(80.0, value))
            elif param == "stop_loss_pct":
                # Limit change to max 0.02 per adjustment
                if old_value is not None:
                    value = max(old_value - 0.02, min(old_value + 0.02, value))
                new_config.stop_loss_pct = max(0.04, min(0.08, value))
            elif param == "position_size_pct":
                # Limit change to max 0.10 per adjustment
                if old_value is not None:
                    value = max(old_value - 0.10, min(old_value + 0.10, value))
                new_config.position_size_pct = max(0.70, min(0.95, value))
            else:
                logger.warning(f"Unknown parameter: {param}")

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

        response = self.call_claude(prompt)
        if not response:
            logger.error("No response from Claude")
            return None

        # Parse response
        result = self.parse_response(response)
        if not result:
            logger.error("Failed to parse Claude response")
            return None

        logger.info(f"Analysis complete: {result.summary}")
        logger.info(f"Confidence: {result.confidence:.1%}")
        logger.info(f"Modifications: {len(result.modifications)}")

        # Check cooldown period before applying
        if auto_apply and result.modifications:
            # Check if we're still in cooldown period
            if self.firestore:
                last_change = self.firestore.get_last_strategy_change_time()
                if last_change:
                    from datetime import timedelta
                    days_since_change = (datetime.now() - last_change).days
                    if days_since_change < cooldown_days:
                        logger.info(
                            f"Cooldown active: {days_since_change} days since last change, "
                            f"waiting {cooldown_days - days_since_change} more days"
                        )
                        return result

        # Auto-apply if enabled and confident
        if auto_apply and result.modifications and result.confidence >= min_confidence:
            # Limit to single modification to prevent oscillation
            if len(result.modifications) > 1:
                logger.info("Multiple modifications suggested, applying only the first one")
                result.modifications = [result.modifications[0]]

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

        elif result.modifications and result.confidence < min_confidence:
            logger.info(
                f"Modifications suggested but confidence ({result.confidence:.1%}) "
                f"below threshold ({min_confidence:.1%})"
            )

        return result


def run_analysis(auto_apply: bool = False) -> Optional[AnalysisResult]:
    """
    Convenience function to run analysis.

    Args:
        auto_apply: Whether to auto-apply modifications

    Returns:
        Analysis result
    """
    try:
        firestore = FirestoreClient()
    except Exception:
        firestore = None
        logger.warning("Firestore not available, running without DB")

    analyzer = ClaudeAnalyzer(firestore_client=firestore)
    return analyzer.analyze(auto_apply=auto_apply)


if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO)

    auto = "--auto" in sys.argv
    result = run_analysis(auto_apply=auto)

    if result:
        print(f"\n=== Analysis Result ===")
        print(f"Summary: {result.summary}")
        print(f"Confidence: {result.confidence:.1%}")
        print(f"Modifications: {len(result.modifications)}")
        for mod in result.modifications:
            print(f"  - {mod.parameter}: {mod.old_value} -> {mod.new_value}")
