use std::time::Instant;

use chrono::{DateTime, Utc};
use common::{BacktestParameters, BacktestResult, Bar, PositionSide, SignalType};

use crate::indicators::{IndicatorSeries, IndicatorValues};
use crate::metrics::MetricsCalculator;
use crate::portfolio::Portfolio;
use crate::signals::SignalGenerator;

/// High-performance backtest engine
pub struct BacktestEngine {
    params: BacktestParameters,
}

impl BacktestEngine {
    pub fn new(params: BacktestParameters) -> Self {
        Self { params }
    }

    /// Run backtest on provided bar data
    pub fn run(&self, bars: &[Bar], hedge_bars: Option<&[Bar]>) -> BacktestResult {
        let start_time = Instant::now();

        // Minimum data check
        let warmup = self.params.sma_period.max(self.params.bb_period);
        if bars.len() < warmup + 1 {
            return self.empty_result(bars);
        }

        // Extract price data
        let closes: Vec<f64> = bars.iter().map(|b| b.close).collect();
        let highs: Vec<f64> = bars.iter().map(|b| b.high).collect();
        let lows: Vec<f64> = bars.iter().map(|b| b.low).collect();

        // Calculate all indicators upfront (vectorized)
        let indicators = IndicatorSeries::calculate(
            &closes,
            &highs,
            &lows,
            self.params.rsi_period,
            self.params.sma_period,
            self.params.bb_period,
            self.params.bb_std_dev,
            14, // ATR period
        );

        // Initialize components
        let mut portfolio = Portfolio::new(self.params.initial_capital);
        let signal_generator = SignalGenerator::new(&self.params);

        // Equity curve tracking
        let mut equity_curve: Vec<(DateTime<Utc>, f64)> = Vec::with_capacity(bars.len());

        // Run simulation
        for i in warmup..bars.len() {
            let bar = &bars[i];
            let hedge_bar = hedge_bars.and_then(|h| h.get(i));

            // Get indicator values for this bar
            let mut ind_values = indicators.get(i);
            ind_values.vwap = bar.vwap;
            if i > 0 {
                ind_values.prev_high = Some(bars[i - 1].high);
                ind_values.prev_low = Some(bars[i - 1].low);
            }

            // Generate and execute signals
            self.process_signals(
                &mut portfolio,
                &signal_generator,
                bar,
                hedge_bar,
                &ind_values,
            );

            // Update portfolio prices
            portfolio.update_prices(bar.close, hedge_bar.map(|h| h.close));

            // Record equity
            equity_curve.push((bar.timestamp, portfolio.equity()));
        }

        // Close any remaining positions at end
        if let Some(last_bar) = bars.last() {
            if portfolio.has_position() {
                portfolio.close_position(last_bar.close, last_bar.timestamp, "end of backtest", 0.0);
            }
            if portfolio.has_hedge_position() {
                if let Some(hedge_bar) = hedge_bars.and_then(|h| h.last()) {
                    portfolio.close_hedge_position(
                        hedge_bar.close,
                        hedge_bar.timestamp,
                        "end of backtest",
                        0.0,
                    );
                }
            }
        }

        // Calculate metrics
        let trades = portfolio.trades().to_vec();
        let metrics =
            MetricsCalculator::calculate(&equity_curve, &trades, self.params.initial_capital);
        let drawdown_curve = MetricsCalculator::calculate_drawdown_curve(&equity_curve);

        let execution_time_ms = start_time.elapsed().as_millis() as u64;

        BacktestResult {
            metrics,
            equity_curve,
            drawdown_curve,
            trades,
            start_date: bars.first().unwrap().timestamp.date_naive(),
            end_date: bars.last().unwrap().timestamp.date_naive(),
            initial_capital: self.params.initial_capital,
            final_equity: portfolio.equity(),
            execution_time_ms,
        }
    }

    /// Process signals and execute trades
    fn process_signals(
        &self,
        portfolio: &mut Portfolio,
        signal_generator: &SignalGenerator,
        bar: &Bar,
        hedge_bar: Option<&Bar>,
        indicators: &IndicatorValues,
    ) {
        // Check for stop loss first
        if portfolio.has_position() && portfolio.check_stop_loss(bar.close) {
            portfolio.close_position(bar.close, bar.timestamp, "stop loss", self.params.commission);
            return;
        }

        // Generate signal
        let signal = signal_generator.generate(
            bar,
            indicators,
            portfolio.has_position(),
            portfolio.current_position(),
            portfolio.has_hedge_position(),
        );

        if let Some(sig) = signal {
            match sig.signal_type {
                SignalType::Buy => {
                    self.execute_buy(portfolio, bar, indicators);
                }
                SignalType::Sell => {
                    portfolio.close_position(
                        bar.close,
                        bar.timestamp,
                        &sig.reason,
                        self.params.commission,
                    );
                }
                SignalType::HedgeBuy => {
                    if let Some(hbar) = hedge_bar {
                        self.execute_hedge_buy(portfolio, hbar);
                    }
                }
                SignalType::HedgeSell => {
                    if let Some(hbar) = hedge_bar {
                        portfolio.close_hedge_position(
                            hbar.close,
                            hbar.timestamp,
                            &sig.reason,
                            self.params.commission,
                        );
                    }
                }
                _ => {}
            }
        }
    }

    /// Execute buy order
    fn execute_buy(&self, portfolio: &mut Portfolio, bar: &Bar, indicators: &IndicatorValues) {
        let quantity = portfolio.calculate_position_size(
            bar.close,
            self.params.position_size_pct,
            self.params.cash_reserve_pct,
        );

        if quantity < 1.0 {
            return;
        }

        // Calculate stop loss price
        let stop_loss_price = if self.params.stop_loss_pct > 0.0 {
            Some(bar.close * (1.0 - self.params.stop_loss_pct))
        } else {
            None
        };

        let _ = portfolio.open_position(
            &self.params.symbol,
            quantity,
            bar.close * (1.0 + self.params.slippage_pct),
            PositionSide::Long,
            bar.timestamp,
            stop_loss_price,
            self.params.commission,
        );
    }

    /// Execute hedge buy order
    fn execute_hedge_buy(&self, portfolio: &mut Portfolio, bar: &Bar) {
        let quantity = portfolio.calculate_position_size(
            bar.close,
            self.params.short_position_size_pct,
            self.params.cash_reserve_pct,
        );

        if quantity < 1.0 {
            return;
        }

        let stop_loss_price = if self.params.short_stop_loss_pct > 0.0 {
            Some(bar.close * (1.0 - self.params.short_stop_loss_pct))
        } else {
            None
        };

        let _ = portfolio.open_position(
            &self.params.inverse_symbol,
            quantity,
            bar.close * (1.0 + self.params.slippage_pct),
            PositionSide::Hedge,
            bar.timestamp,
            stop_loss_price,
            self.params.commission,
        );
    }

    /// Create empty result for insufficient data
    fn empty_result(&self, bars: &[Bar]) -> BacktestResult {
        BacktestResult {
            metrics: Default::default(),
            equity_curve: vec![],
            drawdown_curve: vec![],
            trades: vec![],
            start_date: bars
                .first()
                .map(|b| b.timestamp.date_naive())
                .unwrap_or_else(|| chrono::Utc::now().date_naive()),
            end_date: bars
                .last()
                .map(|b| b.timestamp.date_naive())
                .unwrap_or_else(|| chrono::Utc::now().date_naive()),
            initial_capital: self.params.initial_capital,
            final_equity: self.params.initial_capital,
            execution_time_ms: 0,
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn generate_test_bars(n: usize, base_price: f64) -> Vec<Bar> {
        use chrono::Duration;
        let start = Utc.with_ymd_and_hms(2024, 1, 1, 9, 30, 0).unwrap();
        (0..n)
            .map(|i| {
                let price = base_price + (i as f64 * 0.1).sin() * 5.0;
                Bar {
                    timestamp: start + Duration::days(i as i64),
                    open: price - 0.1,
                    high: price + 0.5,
                    low: price - 0.5,
                    close: price,
                    volume: 1000000,
                    vwap: Some(price + 0.2),
                }
            })
            .collect()
    }

    #[test]
    fn test_backtest_runs() {
        let params = BacktestParameters::default();
        let engine = BacktestEngine::new(params);
        let bars = generate_test_bars(100, 50.0);

        let result = engine.run(&bars, None);

        assert!(result.execution_time_ms >= 0);
        assert_eq!(result.initial_capital, 10000.0);
        assert!(!result.equity_curve.is_empty());
    }

    #[test]
    fn test_backtest_insufficient_data() {
        let params = BacktestParameters::default();
        let engine = BacktestEngine::new(params);
        let bars = generate_test_bars(5, 50.0);

        let result = engine.run(&bars, None);

        assert!(result.equity_curve.is_empty());
        assert_eq!(result.final_equity, 10000.0);
    }

    #[test]
    fn test_backtest_performance() {
        let params = BacktestParameters::default();
        let engine = BacktestEngine::new(params);
        let bars = generate_test_bars(1000, 50.0);

        let result = engine.run(&bars, None);

        // Should complete in under 100ms for 1000 bars
        assert!(result.execution_time_ms < 100);
    }
}
