"""
ATO Tax Report Generator.
"""
import csv
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.constants import ATO_FY_START_DAY, ATO_FY_START_MONTH, ATO_LONG_TERM_DAYS
from config.settings import REPORTS_DIR
from logging_system.trade_logger import TradeLogger

logger = logging.getLogger(__name__)


class ATOTaxReporter:
    """Generate ATO-compliant tax reports."""

    def __init__(
        self,
        trade_logger: Optional[TradeLogger] = None,
        reports_dir: Optional[Path] = None,
    ):
        """
        Initialize tax reporter.

        Args:
            trade_logger: TradeLogger instance
            reports_dir: Directory for reports
        """
        self.trade_logger = trade_logger or TradeLogger()
        self.reports_dir = reports_dir or REPORTS_DIR
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def get_fy_dates(fy_year: int) -> tuple[datetime, datetime]:
        """
        Get start and end dates for Australian fiscal year.

        Args:
            fy_year: Fiscal year (e.g., 2024 for FY2023-24)

        Returns:
            Tuple of (start_date, end_date)
        """
        start = datetime(fy_year - 1, ATO_FY_START_MONTH, ATO_FY_START_DAY)
        end = datetime(fy_year, ATO_FY_START_MONTH - 1, 30, 23, 59, 59)
        return start, end

    @staticmethod
    def get_current_fy() -> int:
        """Get current fiscal year."""
        now = datetime.now()
        if now.month >= ATO_FY_START_MONTH:
            return now.year + 1
        return now.year

    def generate_fy_report(
        self,
        fy_year: Optional[int] = None,
        output_csv: bool = True,
        output_summary: bool = True,
    ) -> dict:
        """
        Generate fiscal year tax report.

        Args:
            fy_year: Fiscal year (defaults to current)
            output_csv: Generate CSV file
            output_summary: Generate text summary

        Returns:
            Report summary dictionary
        """
        fy_year = fy_year or self.get_current_fy()
        start_date, end_date = self.get_fy_dates(fy_year)

        logger.info(f"Generating FY{fy_year-1}-{str(fy_year)[-2:]} report")

        # Get trades for period
        trades = self.trade_logger.get_trades(
            start_date=start_date,
            end_date=end_date,
        )

        # Filter only sells (realized gains/losses)
        sells = [t for t in trades if t["side"] == "SELL" and t.get("realized_pnl_aud") is not None]

        # Categorize gains
        short_term_gains = []
        long_term_gains = []

        for trade in sells:
            holding_days = trade.get("holding_period_days", 0) or 0
            pnl = trade.get("realized_pnl_aud", 0) or 0

            if holding_days >= ATO_LONG_TERM_DAYS:
                long_term_gains.append({
                    "trade": trade,
                    "pnl_aud": pnl,
                    "discounted_pnl": pnl * 0.5 if pnl > 0 else pnl,  # 50% CGT discount
                })
            else:
                short_term_gains.append({
                    "trade": trade,
                    "pnl_aud": pnl,
                })

        # Calculate totals
        total_short_term_gains = sum(g["pnl_aud"] for g in short_term_gains if g["pnl_aud"] > 0)
        total_short_term_losses = sum(g["pnl_aud"] for g in short_term_gains if g["pnl_aud"] < 0)
        total_long_term_gains = sum(g["pnl_aud"] for g in long_term_gains if g["pnl_aud"] > 0)
        total_long_term_losses = sum(g["pnl_aud"] for g in long_term_gains if g["pnl_aud"] < 0)
        total_long_term_discounted = sum(g["discounted_pnl"] for g in long_term_gains if g["pnl_aud"] > 0)

        net_short_term = total_short_term_gains + total_short_term_losses
        net_long_term = total_long_term_gains + total_long_term_losses
        net_long_term_discounted = total_long_term_discounted + total_long_term_losses

        # Calculate taxable gain (apply losses first to non-discounted gains)
        total_losses = total_short_term_losses + total_long_term_losses
        remaining_losses = total_losses

        # Apply losses to short-term gains first
        taxable_short_term = max(0, total_short_term_gains + min(0, remaining_losses))
        remaining_losses = min(0, remaining_losses + total_short_term_gains)

        # Then apply to long-term gains (before discount)
        taxable_long_term_base = max(0, total_long_term_gains + min(0, remaining_losses))
        taxable_long_term = taxable_long_term_base * 0.5  # Apply 50% discount

        total_taxable_gain = taxable_short_term + taxable_long_term

        summary = {
            "fiscal_year": f"FY{fy_year-1}-{str(fy_year)[-2:]}",
            "period_start": start_date.strftime("%Y-%m-%d"),
            "period_end": end_date.strftime("%Y-%m-%d"),
            "total_trades": len(trades),
            "total_sells": len(sells),
            "short_term": {
                "count": len(short_term_gains),
                "total_gains": total_short_term_gains,
                "total_losses": total_short_term_losses,
                "net": net_short_term,
            },
            "long_term": {
                "count": len(long_term_gains),
                "total_gains": total_long_term_gains,
                "total_losses": total_long_term_losses,
                "net": net_long_term,
                "discounted_gains": total_long_term_discounted,
                "net_discounted": net_long_term_discounted,
            },
            "total_taxable_gain_aud": total_taxable_gain,
            "generated_at": datetime.now().isoformat(),
        }

        # Generate files
        if output_csv:
            self._write_csv(fy_year, sells)

        if output_summary:
            self._write_summary(fy_year, summary, short_term_gains, long_term_gains)

        logger.info(f"Report generated: Taxable gain AUD ${total_taxable_gain:,.2f}")

        return summary

    def _write_csv(self, fy_year: int, sells: list[dict]) -> Path:
        """Write detailed CSV report."""
        filename = f"cgt_report_fy{fy_year-1}-{str(fy_year)[-2:]}.csv"
        filepath = self.reports_dir / filename

        fieldnames = [
            "trade_id",
            "date_sold",
            "symbol",
            "quantity",
            "sale_price_usd",
            "sale_value_usd",
            "sale_value_aud",
            "exchange_rate",
            "cost_basis_aud",
            "capital_gain_loss_aud",
            "holding_period_days",
            "eligible_for_discount",
            "discounted_gain_aud",
        ]

        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for trade in sells:
                pnl = trade.get("realized_pnl_aud", 0) or 0
                holding = trade.get("holding_period_days", 0) or 0
                eligible = holding >= ATO_LONG_TERM_DAYS
                discounted = pnl * 0.5 if (pnl > 0 and eligible) else pnl

                # Estimate cost basis
                sale_value = trade.get("total_value_aud", 0)
                cost_basis = sale_value - pnl

                writer.writerow({
                    "trade_id": trade["trade_id"],
                    "date_sold": trade["timestamp_aest"][:10],
                    "symbol": trade["symbol"],
                    "quantity": trade["quantity"],
                    "sale_price_usd": trade["fill_price"],
                    "sale_value_usd": trade["total_value_usd"],
                    "sale_value_aud": trade["total_value_aud"],
                    "exchange_rate": trade["exchange_rate"],
                    "cost_basis_aud": cost_basis,
                    "capital_gain_loss_aud": pnl,
                    "holding_period_days": holding,
                    "eligible_for_discount": "Yes" if eligible else "No",
                    "discounted_gain_aud": discounted,
                })

        logger.info(f"CSV report saved: {filepath}")
        return filepath

    def _write_summary(
        self,
        fy_year: int,
        summary: dict,
        short_term: list,
        long_term: list,
    ) -> Path:
        """Write text summary report."""
        filename = f"cgt_summary_fy{fy_year-1}-{str(fy_year)[-2:]}.txt"
        filepath = self.reports_dir / filename

        with open(filepath, "w") as f:
            f.write("=" * 60 + "\n")
            f.write(f"ATO CAPITAL GAINS TAX REPORT - {summary['fiscal_year']}\n")
            f.write("=" * 60 + "\n\n")

            f.write(f"Period: {summary['period_start']} to {summary['period_end']}\n")
            f.write(f"Report Generated: {summary['generated_at']}\n")
            f.write(f"Strategy: RSI(2) Mean Reversion - TQQQ\n\n")

            f.write("-" * 60 + "\n")
            f.write("SUMMARY\n")
            f.write("-" * 60 + "\n")
            f.write(f"Total Trades: {summary['total_trades']}\n")
            f.write(f"Total Sales: {summary['total_sells']}\n\n")

            f.write("SHORT-TERM CAPITAL GAINS (<12 months):\n")
            st = summary["short_term"]
            f.write(f"  Number of sales: {st['count']}\n")
            f.write(f"  Gross gains:     AUD ${st['total_gains']:>12,.2f}\n")
            f.write(f"  Gross losses:    AUD ${st['total_losses']:>12,.2f}\n")
            f.write(f"  Net result:      AUD ${st['net']:>12,.2f}\n\n")

            f.write("LONG-TERM CAPITAL GAINS (>=12 months):\n")
            lt = summary["long_term"]
            f.write(f"  Number of sales: {lt['count']}\n")
            f.write(f"  Gross gains:     AUD ${lt['total_gains']:>12,.2f}\n")
            f.write(f"  Gross losses:    AUD ${lt['total_losses']:>12,.2f}\n")
            f.write(f"  Net result:      AUD ${lt['net']:>12,.2f}\n")
            f.write(f"  After 50% discount: AUD ${lt['net_discounted']:>12,.2f}\n\n")

            f.write("-" * 60 + "\n")
            f.write(f"TOTAL TAXABLE CAPITAL GAIN: AUD ${summary['total_taxable_gain_aud']:>12,.2f}\n")
            f.write("-" * 60 + "\n\n")

            f.write("NOTES:\n")
            f.write("- All amounts in Australian Dollars (AUD)\n")
            f.write("- Exchange rates sourced at time of each transaction\n")
            f.write("- 50% CGT discount applied to assets held >12 months\n")
            f.write("- Losses offset against gains before discount applied\n")
            f.write("- Consult a tax professional for final return\n")

        logger.info(f"Summary report saved: {filepath}")
        return filepath

    def get_ytd_summary(self) -> dict:
        """Get year-to-date summary."""
        return self.generate_fy_report(
            fy_year=self.get_current_fy(),
            output_csv=False,
            output_summary=False,
        )
