use serde::{Deserialize, Serialize};

/// Backtest parameters
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestParameters {
    // Symbol
    pub symbol: String,
    pub inverse_symbol: String,
    // RSI parameters
    pub rsi_period: usize,
    pub rsi_oversold: f64,
    pub rsi_overbought: f64,
    // SMA parameters
    pub sma_period: usize,
    // Risk management
    pub stop_loss_pct: f64,
    pub position_size_pct: f64,
    pub cash_reserve_pct: f64,
    // Filters
    pub vwap_filter_enabled: bool,
    pub vwap_entry_below: bool,
    pub bb_filter_enabled: bool,
    pub bb_period: usize,
    pub bb_std_dev: f64,
    pub volume_filter_enabled: bool,
    pub volume_min_ratio: f64,
    // Short/Hedge
    pub short_enabled: bool,
    pub use_inverse_etf: bool,
    pub rsi_overbought_short: f64,
    pub rsi_oversold_short: f64,
    pub short_stop_loss_pct: f64,
    pub short_position_size_pct: f64,
    // Backtest settings
    pub initial_capital: f64,
    pub commission: f64,
    pub slippage_pct: f64,
}

impl Default for BacktestParameters {
    fn default() -> Self {
        Self {
            symbol: "TQQQ".to_string(),
            inverse_symbol: "SQQQ".to_string(),
            rsi_period: 2,
            rsi_oversold: 30.0,
            rsi_overbought: 75.0,
            sma_period: 20,
            stop_loss_pct: 0.05,
            position_size_pct: 0.90,
            cash_reserve_pct: 0.10,
            vwap_filter_enabled: true,
            vwap_entry_below: true,
            bb_filter_enabled: false,
            bb_period: 20,
            bb_std_dev: 2.0,
            volume_filter_enabled: false,
            volume_min_ratio: 1.0,
            short_enabled: true,
            use_inverse_etf: true,
            rsi_overbought_short: 90.0,
            rsi_oversold_short: 60.0,
            short_stop_loss_pct: 0.05,
            short_position_size_pct: 0.30,
            initial_capital: 10000.0,
            commission: 0.0,
            slippage_pct: 0.001,
        }
    }
}

impl BacktestParameters {
    pub fn with_capital(mut self, capital: f64) -> Self {
        self.initial_capital = capital;
        self
    }

    pub fn with_rsi_thresholds(mut self, oversold: f64, overbought: f64) -> Self {
        self.rsi_oversold = oversold;
        self.rsi_overbought = overbought;
        self
    }

    pub fn with_stop_loss(mut self, stop_loss_pct: f64) -> Self {
        self.stop_loss_pct = stop_loss_pct;
        self
    }

    pub fn with_sma_period(mut self, period: usize) -> Self {
        self.sma_period = period;
        self
    }

    pub fn without_short(mut self) -> Self {
        self.short_enabled = false;
        self
    }

    pub fn without_vwap_filter(mut self) -> Self {
        self.vwap_filter_enabled = false;
        self
    }
}
