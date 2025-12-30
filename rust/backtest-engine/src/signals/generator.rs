use chrono::{DateTime, Utc};
use common::{BacktestParameters, Bar, Position, PositionSide, Signal, SignalType};

use crate::indicators::IndicatorValues;

/// Signal generator based on RSI(2) mean reversion strategy
pub struct SignalGenerator {
    params: BacktestParameters,
}

impl SignalGenerator {
    pub fn new(params: &BacktestParameters) -> Self {
        Self {
            params: params.clone(),
        }
    }

    /// Generate trading signal based on current market state
    pub fn generate(
        &self,
        bar: &Bar,
        indicators: &IndicatorValues,
        has_position: bool,
        current_position: Option<&Position>,
        has_hedge: bool,
    ) -> Option<Signal> {
        // Check for exit signals first (if we have a position)
        if has_position {
            if let Some(signal) = self.check_exit_signal(bar, indicators, current_position) {
                return Some(signal);
            }
        }

        // Check for hedge signals
        if self.params.short_enabled {
            if has_hedge {
                if let Some(signal) = self.check_hedge_exit_signal(bar, indicators) {
                    return Some(signal);
                }
            } else if !has_position {
                if let Some(signal) = self.check_hedge_entry_signal(bar, indicators) {
                    return Some(signal);
                }
            }
        }

        // Check for entry signals (if no position)
        if !has_position {
            if let Some(signal) = self.check_entry_signal(bar, indicators) {
                return Some(signal);
            }
        }

        None
    }

    /// Check for entry signal (BUY)
    fn check_entry_signal(&self, bar: &Bar, indicators: &IndicatorValues) -> Option<Signal> {
        // RSI oversold condition
        if indicators.rsi > self.params.rsi_oversold {
            return None;
        }

        // VWAP filter: price should be below VWAP for better entry
        if self.params.vwap_filter_enabled && self.params.vwap_entry_below {
            if let Some(vwap) = indicators.vwap.or(bar.vwap) {
                if bar.close >= vwap {
                    return None;
                }
            }
        }

        // SMA trend filter: price should be above SMA (uptrend)
        if let Some(sma) = indicators.sma {
            if bar.close < sma {
                return None;
            }
        }

        // Bollinger Band filter (optional)
        if self.params.bb_filter_enabled && indicators.bb_lower > 0.0 {
            if bar.close > indicators.bb_lower {
                return None;
            }
        }

        // Calculate signal strength (lower RSI = stronger signal)
        let strength = 1.0 - (indicators.rsi / self.params.rsi_oversold);

        Some(Signal {
            timestamp: bar.timestamp,
            signal_type: SignalType::Buy,
            symbol: self.params.symbol.clone(),
            price: bar.close,
            rsi: indicators.rsi,
            reason: format!(
                "RSI({:.1}) <= {:.0}, price below VWAP",
                indicators.rsi, self.params.rsi_oversold
            ),
            strength,
            vwap: indicators.vwap.or(bar.vwap),
            sma: indicators.sma,
        })
    }

    /// Check for exit signal (SELL)
    fn check_exit_signal(
        &self,
        bar: &Bar,
        indicators: &IndicatorValues,
        position: Option<&Position>,
    ) -> Option<Signal> {
        // RSI overbought - take profit
        if indicators.rsi >= self.params.rsi_overbought {
            return Some(Signal {
                timestamp: bar.timestamp,
                signal_type: SignalType::Sell,
                symbol: self.params.symbol.clone(),
                price: bar.close,
                rsi: indicators.rsi,
                reason: format!(
                    "RSI({:.1}) >= {:.0} - take profit",
                    indicators.rsi, self.params.rsi_overbought
                ),
                strength: (indicators.rsi - self.params.rsi_overbought)
                    / (100.0 - self.params.rsi_overbought),
                vwap: indicators.vwap.or(bar.vwap),
                sma: indicators.sma,
            });
        }

        // Stop loss check
        if let Some(pos) = position {
            if let Some(stop_price) = pos.stop_loss_price {
                if bar.close <= stop_price {
                    return Some(Signal {
                        timestamp: bar.timestamp,
                        signal_type: SignalType::Sell,
                        symbol: self.params.symbol.clone(),
                        price: bar.close,
                        rsi: indicators.rsi,
                        reason: format!(
                            "Stop loss triggered at {:.2} (entry: {:.2})",
                            bar.close, pos.avg_entry_price
                        ),
                        strength: 1.0,
                        vwap: indicators.vwap.or(bar.vwap),
                        sma: indicators.sma,
                    });
                }
            }
        }

        None
    }

    /// Check for hedge entry signal (when RSI is extremely overbought)
    fn check_hedge_entry_signal(&self, bar: &Bar, indicators: &IndicatorValues) -> Option<Signal> {
        if indicators.rsi >= self.params.rsi_overbought_short {
            let strength =
                (indicators.rsi - self.params.rsi_overbought_short) / (100.0 - self.params.rsi_overbought_short);

            return Some(Signal {
                timestamp: bar.timestamp,
                signal_type: SignalType::HedgeBuy,
                symbol: self.params.inverse_symbol.clone(),
                price: bar.close,
                rsi: indicators.rsi,
                reason: format!(
                    "RSI({:.1}) >= {:.0} - hedge with {}",
                    indicators.rsi, self.params.rsi_overbought_short, self.params.inverse_symbol
                ),
                strength,
                vwap: indicators.vwap.or(bar.vwap),
                sma: indicators.sma,
            });
        }

        None
    }

    /// Check for hedge exit signal
    fn check_hedge_exit_signal(&self, bar: &Bar, indicators: &IndicatorValues) -> Option<Signal> {
        if indicators.rsi <= self.params.rsi_oversold_short {
            return Some(Signal {
                timestamp: bar.timestamp,
                signal_type: SignalType::HedgeSell,
                symbol: self.params.inverse_symbol.clone(),
                price: bar.close,
                rsi: indicators.rsi,
                reason: format!(
                    "RSI({:.1}) <= {:.0} - close hedge",
                    indicators.rsi, self.params.rsi_oversold_short
                ),
                strength: 1.0 - (indicators.rsi / self.params.rsi_oversold_short),
                vwap: indicators.vwap.or(bar.vwap),
                sma: indicators.sma,
            });
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn make_bar(close: f64) -> Bar {
        Bar {
            timestamp: Utc.with_ymd_and_hms(2024, 1, 1, 12, 0, 0).unwrap(),
            open: close,
            high: close + 0.5,
            low: close - 0.5,
            close,
            volume: 1000000,
            vwap: Some(close + 0.1),
        }
    }

    fn make_indicators(rsi: f64, sma: f64) -> IndicatorValues {
        IndicatorValues {
            rsi,
            sma: Some(sma),
            vwap: None,
            ..Default::default()
        }
    }

    #[test]
    fn test_buy_signal() {
        let params = BacktestParameters::default().without_vwap_filter();
        let generator = SignalGenerator::new(&params);

        let bar = make_bar(50.0);
        let indicators = make_indicators(25.0, 48.0); // RSI < 30, price > SMA

        let signal = generator.generate(&bar, &indicators, false, None, false);

        assert!(signal.is_some());
        let s = signal.unwrap();
        assert_eq!(s.signal_type, SignalType::Buy);
        assert!(s.strength > 0.0);
    }

    #[test]
    fn test_no_buy_when_rsi_high() {
        let params = BacktestParameters::default();
        let generator = SignalGenerator::new(&params);

        let bar = make_bar(50.0);
        let indicators = make_indicators(50.0, 48.0); // RSI > 30

        let signal = generator.generate(&bar, &indicators, false, None, false);

        assert!(signal.is_none());
    }

    #[test]
    fn test_sell_signal_rsi_overbought() {
        let params = BacktestParameters::default();
        let generator = SignalGenerator::new(&params);

        let bar = make_bar(55.0);
        let indicators = make_indicators(80.0, 48.0); // RSI > 75

        let signal = generator.generate(&bar, &indicators, true, None, false);

        assert!(signal.is_some());
        let s = signal.unwrap();
        assert_eq!(s.signal_type, SignalType::Sell);
    }

    #[test]
    fn test_hedge_signal() {
        let params = BacktestParameters::default();
        let generator = SignalGenerator::new(&params);

        let bar = make_bar(55.0);
        let indicators = make_indicators(92.0, 48.0); // RSI > 90

        let signal = generator.generate(&bar, &indicators, false, None, false);

        assert!(signal.is_some());
        let s = signal.unwrap();
        assert_eq!(s.signal_type, SignalType::HedgeBuy);
        assert_eq!(s.symbol, "SQQQ");
    }
}
