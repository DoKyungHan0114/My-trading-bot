use std::path::PathBuf;

use anyhow::Result;
use clap::Parser;

use backtest_engine::{
    generate_synthetic_bars, load_file, BacktestEngine, BacktestParameters, BacktestResult,
};
use common::RealisticExecutionConfig;

#[derive(Parser, Debug)]
#[command(name = "backtest-engine")]
#[command(author = "TQQQ Trading System")]
#[command(version = "0.1.0")]
#[command(about = "High-performance RSI(2) TQQQ backtest engine", long_about = None)]
struct Args {
    /// Number of days to backtest (used with synthetic data)
    #[arg(short, long, default_value = "30")]
    days: usize,

    /// Initial capital
    #[arg(short, long, default_value = "100000")]
    capital: f64,

    /// Data file path (CSV/JSON). If not provided, uses synthetic data.
    #[arg(short = 'f', long)]
    data_file: Option<PathBuf>,

    /// Symbol to trade
    #[arg(short, long, default_value = "TQQQ")]
    symbol: String,

    /// RSI period
    #[arg(long, default_value = "2")]
    rsi_period: usize,

    /// RSI oversold threshold
    #[arg(long, default_value = "30")]
    rsi_oversold: f64,

    /// RSI overbought threshold
    #[arg(long, default_value = "75")]
    rsi_overbought: f64,

    /// SMA period
    #[arg(long, default_value = "20")]
    sma_period: usize,

    /// Stop loss percentage (0.05 = 5%)
    #[arg(long, default_value = "0.05")]
    stop_loss: f64,

    /// Position size percentage (0.9 = 90%)
    #[arg(long, default_value = "0.9")]
    position_size: f64,

    /// Enable short/hedge trading with SQQQ
    #[arg(long)]
    short_enabled: bool,

    /// Disable VWAP filter
    #[arg(long)]
    no_vwap_filter: bool,

    /// Output format (json, text)
    #[arg(short, long, default_value = "json")]
    output: String,

    /// Pretty print JSON output
    #[arg(long)]
    pretty: bool,

    /// Initial price for synthetic data
    #[arg(long, default_value = "50.0")]
    initial_price: f64,

    /// Enable realistic execution simulation
    #[arg(long)]
    realistic: bool,

    /// Enable pessimistic (worst-case) execution simulation
    #[arg(long)]
    pessimistic: bool,
}

fn main() -> Result<()> {
    let args = Args::parse();

    // Build execution config
    let execution = if args.pessimistic {
        eprintln!("Using PESSIMISTIC execution simulation (worst-case)");
        RealisticExecutionConfig::pessimistic()
    } else if args.realistic {
        eprintln!("Using REALISTIC execution simulation");
        RealisticExecutionConfig::realistic()
    } else {
        RealisticExecutionConfig::default()
    };

    // Build parameters
    let params = BacktestParameters {
        symbol: args.symbol.clone(),
        rsi_period: args.rsi_period,
        rsi_oversold: args.rsi_oversold,
        rsi_overbought: args.rsi_overbought,
        sma_period: args.sma_period,
        stop_loss_pct: args.stop_loss,
        position_size_pct: args.position_size,
        short_enabled: args.short_enabled,
        vwap_filter_enabled: !args.no_vwap_filter,
        initial_capital: args.capital,
        execution,
        ..Default::default()
    };

    // Load or generate data
    let bars = if let Some(path) = &args.data_file {
        eprintln!("Loading data from {:?}...", path);
        load_file(path)?
    } else {
        eprintln!(
            "Generating {} days of synthetic data (initial price: ${:.2})...",
            args.days, args.initial_price
        );
        generate_synthetic_bars(args.days, args.initial_price)
    };

    eprintln!("Running backtest with {} bars...", bars.len());

    // Run backtest
    let engine = BacktestEngine::new(params);
    let result = engine.run(&bars, None);

    // Output result
    match args.output.as_str() {
        "json" => {
            let json = if args.pretty {
                serde_json::to_string_pretty(&result)?
            } else {
                serde_json::to_string(&result)?
            };
            println!("{}", json);
        }
        "text" => {
            print_text_report(&result);
        }
        _ => {
            eprintln!("Unknown output format: {}. Using text.", args.output);
            print_text_report(&result);
        }
    }

    Ok(())
}

fn print_text_report(result: &BacktestResult) {
    println!();
    println!("================================================================");
    println!("  BACKTEST REPORT - RSI(2) TQQQ Mean Reversion Strategy");
    println!("================================================================");
    println!();
    println!("  Period: {} to {}", result.start_date, result.end_date);
    println!(
        "  Duration: {} trading days",
        result.equity_curve.len()
    );
    println!("  Execution Time: {}ms", result.execution_time_ms);
    println!();
    println!("----------------------------------------------------------------");
    println!("  CAPITAL");
    println!("----------------------------------------------------------------");
    println!("  Initial Capital:  ${:>12.2}", result.initial_capital);
    println!("  Final Equity:     ${:>12.2}", result.final_equity);
    println!(
        "  Total Return:     ${:>12.2} ({:+.2}%)",
        result.metrics.total_return, result.metrics.total_return_pct
    );
    println!("  CAGR:             {:>12.2}%", result.metrics.cagr);
    println!();
    println!("----------------------------------------------------------------");
    println!("  RISK METRICS");
    println!("----------------------------------------------------------------");
    println!(
        "  Volatility (Ann): {:>12.2}%",
        result.metrics.volatility
    );
    println!(
        "  Sharpe Ratio:     {:>12.3}",
        result.metrics.sharpe_ratio
    );
    println!(
        "  Sortino Ratio:    {:>12.3}",
        result.metrics.sortino_ratio
    );
    println!(
        "  Max Drawdown:     {:>12.2}%",
        result.metrics.max_drawdown
    );
    println!(
        "  Max DD Duration:  {:>12} days",
        result.metrics.max_drawdown_duration_days
    );
    println!(
        "  Calmar Ratio:     {:>12.3}",
        result.metrics.calmar_ratio
    );
    println!();
    println!("----------------------------------------------------------------");
    println!("  TRADE STATISTICS");
    println!("----------------------------------------------------------------");
    println!(
        "  Total Trades:     {:>12}",
        result.metrics.total_trades
    );
    println!(
        "  Winning Trades:   {:>12}",
        result.metrics.winning_trades
    );
    println!(
        "  Losing Trades:    {:>12}",
        result.metrics.losing_trades
    );
    println!("  Win Rate:         {:>12.1}%", result.metrics.win_rate);
    println!(
        "  Avg Win:          ${:>12.2}",
        result.metrics.avg_win
    );
    println!(
        "  Avg Loss:         ${:>12.2}",
        result.metrics.avg_loss
    );
    println!(
        "  Profit Factor:    {:>12.3}",
        result.metrics.profit_factor
    );
    println!(
        "  Expectancy:       ${:>12.2}",
        result.metrics.expectancy
    );
    println!(
        "  Avg Trade Dur.:   {:>12.1} days",
        result.metrics.avg_trade_duration_days
    );
    println!(
        "  Best Trade:       ${:>12.2}",
        result.metrics.best_trade
    );
    println!(
        "  Worst Trade:      ${:>12.2}",
        result.metrics.worst_trade
    );
    println!(
        "  Exposure:         {:>12.1}%",
        result.metrics.exposure_pct
    );
    println!();
    println!("================================================================");

    // Print recent trades if any
    if !result.trades.is_empty() {
        println!();
        println!("  RECENT TRADES (last 5)");
        println!("----------------------------------------------------------------");
        for trade in result.trades.iter().rev().take(5) {
            let exit_date = trade
                .exit_date
                .map(|d| d.format("%Y-%m-%d").to_string())
                .unwrap_or_else(|| "open".to_string());
            println!(
                "  {} -> {} | P&L: ${:+.2} ({:+.1}%) | {} days",
                trade.entry_date.format("%Y-%m-%d"),
                exit_date,
                trade.pnl,
                trade.pnl_pct,
                trade.holding_days
            );
        }
        println!();
    }
}
