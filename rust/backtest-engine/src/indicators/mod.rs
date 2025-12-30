pub mod atr;
pub mod bollinger;
pub mod ema;
pub mod rsi;
pub mod sma;

pub use atr::{calculate_atr, true_range};
pub use bollinger::{calculate_bollinger_bands, bandwidth, percent_b, BollingerBands};
pub use ema::{calculate_ema, calculate_ema_with_sma_seed};
pub use rsi::calculate_rsi;
pub use sma::{calculate_sma, calculate_sma_filled};

/// Container for all calculated indicators at a specific point
#[derive(Debug, Clone, Default)]
pub struct IndicatorValues {
    pub rsi: f64,
    pub sma: Option<f64>,
    pub ema: f64,
    pub atr: f64,
    pub bb_upper: f64,
    pub bb_middle: f64,
    pub bb_lower: f64,
    pub vwap: Option<f64>,
    pub prev_high: Option<f64>,
    pub prev_low: Option<f64>,
}

/// Pre-computed indicators for all bars
#[derive(Debug)]
pub struct IndicatorSeries {
    pub rsi: Vec<f64>,
    pub sma: Vec<Option<f64>>,
    pub ema: Vec<f64>,
    pub atr: Vec<f64>,
    pub bb: BollingerBands,
}

impl IndicatorSeries {
    /// Calculate all indicators from price data
    pub fn calculate(
        closes: &[f64],
        highs: &[f64],
        lows: &[f64],
        rsi_period: usize,
        sma_period: usize,
        bb_period: usize,
        bb_std_dev: f64,
        atr_period: usize,
    ) -> Self {
        Self {
            rsi: calculate_rsi(closes, rsi_period),
            sma: calculate_sma(closes, sma_period),
            ema: calculate_ema(closes, sma_period),
            atr: calculate_atr(highs, lows, closes, atr_period),
            bb: calculate_bollinger_bands(closes, bb_period, bb_std_dev),
        }
    }

    /// Get indicator values at a specific index
    pub fn get(&self, idx: usize) -> IndicatorValues {
        IndicatorValues {
            rsi: self.rsi.get(idx).copied().unwrap_or(50.0),
            sma: self.sma.get(idx).copied().flatten(),
            ema: self.ema.get(idx).copied().unwrap_or(0.0),
            atr: self.atr.get(idx).copied().unwrap_or(0.0),
            bb_upper: self.bb.upper.get(idx).copied().unwrap_or(0.0),
            bb_middle: self.bb.middle.get(idx).copied().unwrap_or(0.0),
            bb_lower: self.bb.lower.get(idx).copied().unwrap_or(0.0),
            vwap: None,
            prev_high: None,
            prev_low: None,
        }
    }
}
