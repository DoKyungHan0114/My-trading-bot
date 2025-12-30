use chrono::{DateTime, Utc};
use common::{PerformanceMetrics, Trade};

const TRADING_DAYS_PER_YEAR: f64 = 252.0;
const RISK_FREE_RATE: f64 = 0.05; // 5% annual risk-free rate

/// Calculate performance metrics from equity curve and trades
pub struct MetricsCalculator;

impl MetricsCalculator {
    /// Calculate all performance metrics
    pub fn calculate(
        equity_curve: &[(DateTime<Utc>, f64)],
        trades: &[Trade],
        initial_capital: f64,
    ) -> PerformanceMetrics {
        if equity_curve.is_empty() {
            return PerformanceMetrics::default();
        }

        let final_equity = equity_curve.last().map(|(_, e)| *e).unwrap_or(initial_capital);
        let total_return = final_equity - initial_capital;
        let total_return_pct = (total_return / initial_capital) * 100.0;

        // Calculate daily returns
        let daily_returns = Self::calculate_daily_returns(equity_curve);

        // Calculate metrics
        let volatility = Self::calculate_volatility(&daily_returns);
        let sharpe_ratio = Self::calculate_sharpe_ratio(&daily_returns, volatility);
        let sortino_ratio = Self::calculate_sortino_ratio(&daily_returns);
        let (max_drawdown, max_dd_duration) = Self::calculate_max_drawdown(equity_curve);

        // CAGR
        let days = equity_curve.len() as f64;
        let years = days / TRADING_DAYS_PER_YEAR;
        let cagr = if years > 0.0 && final_equity > 0.0 && initial_capital > 0.0 {
            ((final_equity / initial_capital).powf(1.0 / years) - 1.0) * 100.0
        } else {
            0.0
        };

        // Calmar ratio
        let calmar_ratio = if max_drawdown != 0.0 {
            cagr / max_drawdown.abs()
        } else {
            0.0
        };

        // Trade statistics
        let (trade_stats, best_trade, worst_trade) = Self::calculate_trade_stats(trades);

        // Exposure percentage
        let exposure_pct = Self::calculate_exposure(equity_curve, trades);

        PerformanceMetrics {
            total_return,
            total_return_pct,
            cagr,
            volatility,
            sharpe_ratio,
            sortino_ratio,
            max_drawdown,
            max_drawdown_duration_days: max_dd_duration,
            calmar_ratio,
            total_trades: trades.len() as u32,
            winning_trades: trade_stats.winning,
            losing_trades: trade_stats.losing,
            win_rate: trade_stats.win_rate,
            avg_win: trade_stats.avg_win,
            avg_loss: trade_stats.avg_loss,
            profit_factor: trade_stats.profit_factor,
            expectancy: trade_stats.expectancy,
            avg_trade_duration_days: trade_stats.avg_duration,
            best_trade,
            worst_trade,
            exposure_pct,
        }
    }

    /// Calculate daily returns from equity curve
    fn calculate_daily_returns(equity_curve: &[(DateTime<Utc>, f64)]) -> Vec<f64> {
        if equity_curve.len() < 2 {
            return vec![];
        }

        equity_curve
            .windows(2)
            .map(|w| {
                let prev = w[0].1;
                let curr = w[1].1;
                if prev != 0.0 {
                    (curr - prev) / prev
                } else {
                    0.0
                }
            })
            .collect()
    }

    /// Calculate annualized volatility
    fn calculate_volatility(daily_returns: &[f64]) -> f64 {
        if daily_returns.is_empty() {
            return 0.0;
        }

        let n = daily_returns.len() as f64;
        let mean: f64 = daily_returns.iter().sum::<f64>() / n;
        let variance: f64 = daily_returns.iter().map(|r| (r - mean).powi(2)).sum::<f64>() / n;

        variance.sqrt() * TRADING_DAYS_PER_YEAR.sqrt() * 100.0
    }

    /// Calculate Sharpe ratio
    fn calculate_sharpe_ratio(daily_returns: &[f64], volatility: f64) -> f64 {
        if daily_returns.is_empty() || volatility == 0.0 {
            return 0.0;
        }

        let n = daily_returns.len() as f64;
        let mean_daily_return = daily_returns.iter().sum::<f64>() / n;
        let annualized_return = mean_daily_return * TRADING_DAYS_PER_YEAR * 100.0;

        (annualized_return - RISK_FREE_RATE * 100.0) / volatility
    }

    /// Calculate Sortino ratio (uses only downside deviation)
    fn calculate_sortino_ratio(daily_returns: &[f64]) -> f64 {
        if daily_returns.is_empty() {
            return 0.0;
        }

        let n = daily_returns.len() as f64;
        let mean_return = daily_returns.iter().sum::<f64>() / n;
        let daily_risk_free = RISK_FREE_RATE / TRADING_DAYS_PER_YEAR;

        // Calculate downside deviation (only negative returns relative to target)
        let downside_returns: Vec<f64> = daily_returns
            .iter()
            .filter(|&&r| r < daily_risk_free)
            .map(|&r| (r - daily_risk_free).powi(2))
            .collect();

        if downside_returns.is_empty() {
            return f64::INFINITY;
        }

        let downside_variance: f64 = downside_returns.iter().sum::<f64>() / n;
        let downside_deviation = downside_variance.sqrt() * TRADING_DAYS_PER_YEAR.sqrt();

        if downside_deviation == 0.0 {
            return 0.0;
        }

        let annualized_return = mean_return * TRADING_DAYS_PER_YEAR;
        (annualized_return - RISK_FREE_RATE) / downside_deviation
    }

    /// Calculate maximum drawdown and duration
    fn calculate_max_drawdown(equity_curve: &[(DateTime<Utc>, f64)]) -> (f64, i64) {
        if equity_curve.is_empty() {
            return (0.0, 0);
        }

        let mut max_equity = equity_curve[0].1;
        let mut max_drawdown = 0.0;
        let mut max_dd_start = 0;
        let mut max_dd_duration = 0i64;
        let mut current_dd_start = 0;

        for (i, (_, equity)) in equity_curve.iter().enumerate() {
            if *equity > max_equity {
                max_equity = *equity;
                current_dd_start = i;
            }

            let drawdown = (max_equity - equity) / max_equity * 100.0;
            if drawdown > max_drawdown {
                max_drawdown = drawdown;
                max_dd_start = current_dd_start;
                max_dd_duration = (i - max_dd_start) as i64;
            }
        }

        (max_drawdown, max_dd_duration)
    }

    /// Calculate drawdown curve
    pub fn calculate_drawdown_curve(
        equity_curve: &[(DateTime<Utc>, f64)],
    ) -> Vec<(DateTime<Utc>, f64)> {
        if equity_curve.is_empty() {
            return vec![];
        }

        let mut max_equity = equity_curve[0].1;
        equity_curve
            .iter()
            .map(|(ts, equity)| {
                if *equity > max_equity {
                    max_equity = *equity;
                }
                let drawdown = if max_equity > 0.0 {
                    (max_equity - equity) / max_equity * 100.0
                } else {
                    0.0
                };
                (*ts, drawdown)
            })
            .collect()
    }

    /// Calculate trade statistics
    fn calculate_trade_stats(trades: &[Trade]) -> (TradeStats, f64, f64) {
        if trades.is_empty() {
            return (TradeStats::default(), 0.0, 0.0);
        }

        let mut winning = 0u32;
        let mut losing = 0u32;
        let mut total_wins = 0.0;
        let mut total_losses = 0.0;
        let mut total_duration = 0i64;
        let mut best = f64::MIN;
        let mut worst = f64::MAX;

        for trade in trades {
            if trade.pnl > 0.0 {
                winning += 1;
                total_wins += trade.pnl;
            } else if trade.pnl < 0.0 {
                losing += 1;
                total_losses += trade.pnl.abs();
            }

            total_duration += trade.holding_days;
            best = best.max(trade.pnl);
            worst = worst.min(trade.pnl);
        }

        let n = trades.len() as f64;
        let win_rate = if n > 0.0 {
            (winning as f64 / n) * 100.0
        } else {
            0.0
        };

        let avg_win = if winning > 0 {
            total_wins / winning as f64
        } else {
            0.0
        };

        let avg_loss = if losing > 0 {
            total_losses / losing as f64
        } else {
            0.0
        };

        let profit_factor = if total_losses > 0.0 {
            total_wins / total_losses
        } else if total_wins > 0.0 {
            f64::INFINITY
        } else {
            0.0
        };

        let expectancy =
            (win_rate / 100.0 * avg_win) - ((1.0 - win_rate / 100.0) * avg_loss);

        let avg_duration = total_duration as f64 / n;

        (
            TradeStats {
                winning,
                losing,
                win_rate,
                avg_win,
                avg_loss,
                profit_factor,
                expectancy,
                avg_duration,
            },
            if best == f64::MIN { 0.0 } else { best },
            if worst == f64::MAX { 0.0 } else { worst },
        )
    }

    /// Calculate exposure percentage
    fn calculate_exposure(
        equity_curve: &[(DateTime<Utc>, f64)],
        trades: &[Trade],
    ) -> f64 {
        if equity_curve.is_empty() || trades.is_empty() {
            return 0.0;
        }

        let total_days = equity_curve.len() as f64;
        let invested_days: i64 = trades.iter().map(|t| t.holding_days.max(1)).sum();

        (invested_days as f64 / total_days * 100.0).min(100.0)
    }
}

#[derive(Debug, Default)]
struct TradeStats {
    winning: u32,
    losing: u32,
    win_rate: f64,
    avg_win: f64,
    avg_loss: f64,
    profit_factor: f64,
    expectancy: f64,
    avg_duration: f64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn make_equity_curve(values: &[f64]) -> Vec<(DateTime<Utc>, f64)> {
        values
            .iter()
            .enumerate()
            .map(|(i, &v)| {
                (
                    Utc.with_ymd_and_hms(2024, 1, 1 + i as u32, 12, 0, 0).unwrap(),
                    v,
                )
            })
            .collect()
    }

    #[test]
    fn test_basic_metrics() {
        let equity = make_equity_curve(&[10000.0, 10100.0, 10200.0, 10300.0, 10400.0]);
        let trades = vec![];

        let metrics = MetricsCalculator::calculate(&equity, &trades, 10000.0);

        assert_eq!(metrics.total_return, 400.0);
        assert_eq!(metrics.total_return_pct, 4.0);
    }

    #[test]
    fn test_max_drawdown() {
        let equity = make_equity_curve(&[10000.0, 11000.0, 9000.0, 9500.0, 10500.0]);
        let (max_dd, _) = MetricsCalculator::calculate_max_drawdown(&equity);

        // Peak was 11000, trough was 9000 = 18.18% drawdown
        assert!((max_dd - 18.18).abs() < 0.1);
    }

    #[test]
    fn test_sharpe_ratio_positive() {
        // Consistently positive returns should give positive Sharpe
        let equity = make_equity_curve(&[
            10000.0, 10100.0, 10200.0, 10300.0, 10400.0, 10500.0, 10600.0,
        ]);
        let metrics = MetricsCalculator::calculate(&equity, &[], 10000.0);

        assert!(metrics.sharpe_ratio > 0.0);
    }

    #[test]
    fn test_drawdown_curve() {
        let equity = make_equity_curve(&[10000.0, 11000.0, 10000.0, 9000.0]);
        let dd_curve = MetricsCalculator::calculate_drawdown_curve(&equity);

        assert_eq!(dd_curve.len(), 4);
        assert_eq!(dd_curve[0].1, 0.0); // No drawdown at start
        assert_eq!(dd_curve[1].1, 0.0); // New high, no drawdown
        assert!((dd_curve[2].1 - 9.09).abs() < 0.1); // 10000/11000 = ~9.09%
        assert!((dd_curve[3].1 - 18.18).abs() < 0.1); // 9000/11000 = ~18.18%
    }
}
