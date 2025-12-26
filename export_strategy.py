#!/usr/bin/env python3
"""
Export trading strategy configuration to JSON.

Usage:
    ./export_strategy.py                      # Print to stdout
    ./export_strategy.py -o strategy.json     # Save to file
    ./export_strategy.py --pretty             # Pretty print
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
import importlib.util

# Load constants.py directly without importing the config package
constants_path = Path(__file__).parent / "config" / "constants.py"
spec = importlib.util.spec_from_file_location("constants", constants_path)
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)


def build_strategy_config() -> dict:
    """Build strategy configuration dictionary from constants."""
    return {
        "meta": {
            "name": c.STRATEGY_NAME,
            "version": "1.0.0",
            "exported_at": datetime.now().isoformat(),
            "source_symbol": c.SYMBOL,
        },
        "indicators": {
            "rsi": {
                "period": c.RSI_PERIOD,
            },
            "sma": {
                "period": c.SMA_PERIOD,
            },
            "atr": {
                "period": c.ATR_PERIOD,
                "enabled": c.ATR_STOP_ENABLED,
            },
            "bollinger_bands": {
                "period": c.BB_PERIOD,
                "std_dev": c.BB_STD_DEV,
                "enabled": c.BB_FILTER_ENABLED,
            },
            "volume": {
                "avg_period": c.VOLUME_AVG_PERIOD,
                "min_ratio": c.VOLUME_MIN_RATIO,
                "enabled": c.VOLUME_FILTER_ENABLED,
            },
            "vwap": {
                "enabled": c.VWAP_FILTER_ENABLED,
                "entry_below": c.VWAP_ENTRY_BELOW,
            },
        },
        "entry": {
            "long": {
                "conditions": [
                    {
                        "indicator": "rsi",
                        "operator": "<=",
                        "value": c.RSI_OVERSOLD,
                        "required": True,
                    },
                ],
                "filters": {
                    "vwap": {
                        "enabled": c.VWAP_FILTER_ENABLED,
                        "price_below_vwap": c.VWAP_ENTRY_BELOW,
                    },
                    "bollinger": {
                        "enabled": c.BB_FILTER_ENABLED,
                        "price_below_lower": True,
                    },
                    "volume": {
                        "enabled": c.VOLUME_FILTER_ENABLED,
                        "min_ratio": c.VOLUME_MIN_RATIO,
                    },
                },
            },
            "hedge": {
                "enabled": c.SHORT_ENABLED,
                "instrument": c.INVERSE_SYMBOL,
                "use_inverse_etf": c.USE_INVERSE_ETF,
                "conditions": [
                    {
                        "indicator": "rsi",
                        "operator": ">=",
                        "value": c.RSI_OVERBOUGHT_SHORT,
                        "required": True,
                    },
                    {
                        "indicator": "price_vs_sma",
                        "operator": ">",
                        "value": 0,
                        "required": True,
                        "description": "Price above SMA",
                    },
                ],
            },
        },
        "exit": {
            "long": {
                "conditions": [
                    {
                        "indicator": "rsi",
                        "operator": ">=",
                        "value": c.RSI_OVERBOUGHT,
                        "description": "RSI overbought exit",
                    },
                    {
                        "type": "prev_high_breakout",
                        "description": "Close > Previous day high",
                    },
                    {
                        "type": "stop_loss",
                        "value": c.STOP_LOSS_PCT,
                        "description": f"{c.STOP_LOSS_PCT * 100}% stop loss",
                    },
                ],
                "logic": "OR",
            },
            "hedge": {
                "conditions": [
                    {
                        "indicator": "rsi",
                        "operator": "<=",
                        "value": c.RSI_OVERSOLD_SHORT,
                        "description": "RSI mean reversion complete",
                    },
                    {
                        "type": "stop_loss",
                        "value": c.SHORT_STOP_LOSS_PCT,
                        "description": f"{c.SHORT_STOP_LOSS_PCT * 100}% stop loss",
                    },
                ],
                "logic": "OR",
            },
        },
        "risk": {
            "stop_loss_pct": c.STOP_LOSS_PCT,
            "position_size_pct": c.POSITION_SIZE_PCT,
            "cash_reserve_pct": c.CASH_RESERVE_PCT,
            "hedge_position_size_pct": c.SHORT_POSITION_SIZE_PCT,
            "atr_stop": {
                "enabled": c.ATR_STOP_ENABLED,
                "multiplier": c.ATR_STOP_MULTIPLIER,
            },
        },
    }


def main():
    parser = argparse.ArgumentParser(
        description="Export trading strategy to JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python export_strategy.py                    # Print to stdout
  python export_strategy.py -o my_strategy.json
  python export_strategy.py --pretty -o strategy.json
        """,
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON with indentation",
    )

    args = parser.parse_args()

    config = build_strategy_config()

    indent = 2 if args.pretty else None
    json_str = json.dumps(config, indent=indent, ensure_ascii=False)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(json_str, encoding="utf-8")
        print(f"Strategy exported to: {output_path.absolute()}")
    else:
        print(json_str)


if __name__ == "__main__":
    main()
