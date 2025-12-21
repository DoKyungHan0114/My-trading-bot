"""
PDF Report Generator for backtest results.
"""
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np

logger = logging.getLogger(__name__)


class PDFReportGenerator:
    """Generate PDF reports from backtest results."""

    def __init__(self, output_dir: Optional[Path] = None):
        """
        Initialize PDF generator.

        Args:
            output_dir: Directory to save PDFs
        """
        self.output_dir = output_dir or Path("reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def generate(self, result, filename: Optional[str] = None) -> Path:
        """
        Generate PDF report from backtest result.

        Args:
            result: BacktestResult object
            filename: Optional filename (auto-generated if not provided)

        Returns:
            Path to generated PDF
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"backtest_report_{timestamp}.pdf"

        filepath = self.output_dir / filename

        with PdfPages(filepath) as pdf:
            # Page 1: Summary
            self._create_summary_page(result, pdf)

            # Page 2: Equity Curve & Drawdown
            self._create_equity_page(result, pdf)

            # Page 3: Trade Analysis
            self._create_trades_page(result, pdf)

            # Page 4: Trade List
            self._create_trade_list_page(result, pdf)

        logger.info(f"PDF report saved: {filepath}")
        return filepath

    def _create_summary_page(self, result, pdf):
        """Create summary page with key metrics."""
        fig, ax = plt.subplots(figsize=(11, 8.5))
        ax.axis('off')

        # Title
        fig.text(0.5, 0.95, 'TQQQ RSI(2) Mean Reversion Strategy',
                 ha='center', va='top', fontsize=20, fontweight='bold')
        fig.text(0.5, 0.90, 'Backtest Report',
                 ha='center', va='top', fontsize=16, color='gray')

        # Period info
        fig.text(0.5, 0.85, f"Period: {result.start_date} to {result.end_date}",
                 ha='center', va='top', fontsize=12)

        # Key metrics box
        metrics = result.metrics
        y_start = 0.75

        # Left column - Returns
        left_x = 0.15
        fig.text(left_x, y_start, 'PERFORMANCE', fontsize=14, fontweight='bold')

        metrics_left = [
            ('Initial Capital', f'${result.initial_capital:,.2f}'),
            ('Final Equity', f'${result.final_equity:,.2f}'),
            ('Total Return', f'${metrics.total_return:,.2f} ({metrics.total_return_pct:+.2f}%)'),
            ('CAGR', f'{metrics.cagr:+.2f}%'),
            ('Sharpe Ratio', f'{metrics.sharpe_ratio:.3f}'),
            ('Sortino Ratio', f'{metrics.sortino_ratio:.3f}'),
            ('Max Drawdown', f'{metrics.max_drawdown:.2f}%'),
            ('Volatility', f'{metrics.volatility:.2f}%'),
        ]

        for i, (label, value) in enumerate(metrics_left):
            y = y_start - 0.05 - (i * 0.045)
            fig.text(left_x, y, f'{label}:', fontsize=10)
            fig.text(left_x + 0.25, y, value, fontsize=10, fontweight='bold')

        # Right column - Trade Stats
        right_x = 0.55
        fig.text(right_x, y_start, 'TRADE STATISTICS', fontsize=14, fontweight='bold')

        metrics_right = [
            ('Total Trades', f'{metrics.total_trades}'),
            ('Winning Trades', f'{metrics.winning_trades}'),
            ('Losing Trades', f'{metrics.losing_trades}'),
            ('Win Rate', f'{metrics.win_rate:.1f}%'),
            ('Profit Factor', f'{metrics.profit_factor:.3f}'),
            ('Avg Win', f'${metrics.avg_win:.2f}'),
            ('Avg Loss', f'${metrics.avg_loss:.2f}'),
            ('Avg Duration', f'{metrics.avg_trade_duration_days:.1f} days'),
        ]

        for i, (label, value) in enumerate(metrics_right):
            y = y_start - 0.05 - (i * 0.045)
            fig.text(right_x, y, f'{label}:', fontsize=10)
            fig.text(right_x + 0.22, y, value, fontsize=10, fontweight='bold')

        # Parameters box
        y_params = 0.25
        fig.text(0.15, y_params, 'STRATEGY PARAMETERS', fontsize=14, fontweight='bold')

        params = result.parameters
        param_text = (
            f"Symbol: {params.get('symbol', 'TQQQ')}  |  "
            f"RSI Period: {params.get('rsi_period', 2)}  |  "
            f"RSI Oversold: {params.get('rsi_oversold', 10)}  |  "
            f"RSI Overbought: {params.get('rsi_overbought', 70)}  |  "
            f"SMA Period: {params.get('sma_period', 200)}  |  "
            f"Stop Loss: {params.get('stop_loss_pct', 0.05)*100:.1f}%"
        )
        fig.text(0.15, y_params - 0.05, param_text, fontsize=9)

        # Footer
        fig.text(0.5, 0.05, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 ha='center', fontsize=8, color='gray')

        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    def _create_equity_page(self, result, pdf):
        """Create equity curve and drawdown page."""
        fig, axes = plt.subplots(2, 1, figsize=(11, 8.5))

        # Equity Curve
        ax1 = axes[0]
        if len(result.equity_curve) > 0:
            ax1.plot(result.equity_curve.index, result.equity_curve.values,
                    'b-', linewidth=1.5, label='Portfolio Value')
            ax1.axhline(y=result.initial_capital, color='gray',
                       linestyle='--', alpha=0.5, label='Initial Capital')
            ax1.fill_between(result.equity_curve.index,
                           result.initial_capital,
                           result.equity_curve.values,
                           where=result.equity_curve.values >= result.initial_capital,
                           color='green', alpha=0.2)
            ax1.fill_between(result.equity_curve.index,
                           result.initial_capital,
                           result.equity_curve.values,
                           where=result.equity_curve.values < result.initial_capital,
                           color='red', alpha=0.2)

        ax1.set_title('Equity Curve', fontsize=14, fontweight='bold')
        ax1.set_ylabel('Portfolio Value ($)')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax1.xaxis.get_majorticklabels(), rotation=45)

        # Drawdown
        ax2 = axes[1]
        if len(result.drawdown_curve) > 0:
            ax2.fill_between(result.drawdown_curve.index,
                           result.drawdown_curve.values, 0,
                           color='red', alpha=0.3)
            ax2.plot(result.drawdown_curve.index, result.drawdown_curve.values,
                    'r-', linewidth=1)

        ax2.set_title('Drawdown', fontsize=14, fontweight='bold')
        ax2.set_ylabel('Drawdown (%)')
        ax2.set_xlabel('Date')
        ax2.grid(True, alpha=0.3)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.setp(ax2.xaxis.get_majorticklabels(), rotation=45)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    def _create_trades_page(self, result, pdf):
        """Create trade analysis page."""
        fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))

        trades = result.trades
        pnls = [t.pnl for t in trades if t.pnl != 0]
        pnl_pcts = [t.pnl_pct for t in trades if t.pnl_pct != 0]
        holding_days = [t.holding_days for t in trades if t.holding_days > 0]

        # Trade P&L Distribution
        ax1 = axes[0, 0]
        if pnls:
            colors = ['green' if p > 0 else 'red' for p in pnls]
            ax1.bar(range(len(pnls)), pnls, color=colors, alpha=0.7)
            ax1.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax1.set_title('Trade P&L ($)', fontsize=12, fontweight='bold')
        ax1.set_xlabel('Trade #')
        ax1.set_ylabel('P&L ($)')
        ax1.grid(True, alpha=0.3)

        # P&L Histogram
        ax2 = axes[0, 1]
        if pnl_pcts:
            ax2.hist(pnl_pcts, bins=20, color='steelblue', alpha=0.7, edgecolor='black')
            ax2.axvline(x=0, color='red', linestyle='--', linewidth=1)
            ax2.axvline(x=np.mean(pnl_pcts), color='green', linestyle='--',
                       linewidth=1, label=f'Mean: {np.mean(pnl_pcts):.2f}%')
        ax2.set_title('P&L Distribution (%)', fontsize=12, fontweight='bold')
        ax2.set_xlabel('P&L (%)')
        ax2.set_ylabel('Frequency')
        ax2.legend()
        ax2.grid(True, alpha=0.3)

        # Holding Period Distribution
        ax3 = axes[1, 0]
        if holding_days:
            ax3.hist(holding_days, bins=min(20, len(set(holding_days))),
                    color='purple', alpha=0.7, edgecolor='black')
            ax3.axvline(x=np.mean(holding_days), color='orange', linestyle='--',
                       linewidth=1, label=f'Mean: {np.mean(holding_days):.1f} days')
        ax3.set_title('Holding Period Distribution', fontsize=12, fontweight='bold')
        ax3.set_xlabel('Days')
        ax3.set_ylabel('Frequency')
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Cumulative P&L
        ax4 = axes[1, 1]
        if pnls:
            cumulative = np.cumsum(pnls)
            ax4.plot(range(len(cumulative)), cumulative, 'b-', linewidth=2)
            ax4.fill_between(range(len(cumulative)), 0, cumulative,
                           where=np.array(cumulative) >= 0, color='green', alpha=0.2)
            ax4.fill_between(range(len(cumulative)), 0, cumulative,
                           where=np.array(cumulative) < 0, color='red', alpha=0.2)
            ax4.axhline(y=0, color='black', linestyle='-', linewidth=0.5)
        ax4.set_title('Cumulative P&L', fontsize=12, fontweight='bold')
        ax4.set_xlabel('Trade #')
        ax4.set_ylabel('Cumulative P&L ($)')
        ax4.grid(True, alpha=0.3)

        plt.tight_layout()
        pdf.savefig(fig, bbox_inches='tight')
        plt.close(fig)

    def _create_trade_list_page(self, result, pdf):
        """Create trade list table page."""
        trades = result.trades

        if not trades:
            return

        # Split trades into pages of 25
        trades_per_page = 25

        for page_start in range(0, len(trades), trades_per_page):
            page_trades = trades[page_start:page_start + trades_per_page]

            fig, ax = plt.subplots(figsize=(11, 8.5))
            ax.axis('off')

            # Title
            page_num = page_start // trades_per_page + 1
            total_pages = (len(trades) - 1) // trades_per_page + 1
            fig.text(0.5, 0.97, f'Trade List (Page {page_num}/{total_pages})',
                    ha='center', fontsize=14, fontweight='bold')

            # Table headers
            headers = ['#', 'Entry Date', 'Exit Date', 'Entry $', 'Exit $', 'Qty', 'P&L $', 'P&L %', 'Days']
            col_widths = [0.05, 0.14, 0.14, 0.10, 0.10, 0.08, 0.12, 0.10, 0.07]
            col_x = [0.05]
            for w in col_widths[:-1]:
                col_x.append(col_x[-1] + w)

            y = 0.92
            for i, header in enumerate(headers):
                fig.text(col_x[i], y, header, fontsize=9, fontweight='bold')

            # Table rows
            for j, trade in enumerate(page_trades):
                y = 0.88 - (j * 0.032)
                trade_num = page_start + j + 1

                entry_date = trade.entry_date.strftime('%Y-%m-%d') if trade.entry_date else '-'
                exit_date = trade.exit_date.strftime('%Y-%m-%d') if trade.exit_date else '-'

                row_data = [
                    str(trade_num),
                    entry_date,
                    exit_date,
                    f'${trade.entry_price:.2f}',
                    f'${trade.exit_price:.2f}' if trade.exit_price else '-',
                    f'{trade.quantity:.1f}',
                    f'${trade.pnl:+.2f}',
                    f'{trade.pnl_pct:+.2f}%',
                    str(trade.holding_days),
                ]

                # Color based on P&L
                color = 'green' if trade.pnl > 0 else 'red' if trade.pnl < 0 else 'black'

                for i, data in enumerate(row_data):
                    text_color = color if i in [6, 7] else 'black'
                    fig.text(col_x[i], y, data, fontsize=8, color=text_color)

            pdf.savefig(fig, bbox_inches='tight')
            plt.close(fig)
