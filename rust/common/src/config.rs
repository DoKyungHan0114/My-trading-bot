use serde::{Deserialize, Serialize};

/// Realistic execution simulation settings
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RealisticExecutionConfig {
    /// Enable realistic execution simulation
    pub enabled: bool,

    // === Slippage Settings ===
    /// Minimum slippage (can be negative for favorable fills)
    pub slippage_min_pct: f64,
    /// Maximum slippage (typically positive, unfavorable)
    pub slippage_max_pct: f64,
    /// Probability of unfavorable slippage (0.0 - 1.0)
    pub slippage_adverse_probability: f64,

    // === Spread Settings ===
    /// Enable bid/ask spread simulation
    pub spread_enabled: bool,
    /// Base spread as percentage of price
    pub spread_base_pct: f64,
    /// Additional spread during high volatility (multiplier)
    pub spread_volatility_multiplier: f64,

    // === Volume Constraints ===
    /// Enable volume-based fill constraints
    pub volume_limit_enabled: bool,
    /// Maximum percentage of bar volume that can be filled
    pub volume_participation_max_pct: f64,
    /// Enable partial fills when order exceeds volume limit
    pub partial_fill_enabled: bool,

    // === Latency Simulation ===
    /// Number of bars to delay order execution (0 = same bar)
    pub latency_bars: usize,

    // === Market Impact ===
    /// Enable market impact simulation for large orders
    pub market_impact_enabled: bool,
    /// Impact factor: price moves by this % per 1% of daily volume
    pub market_impact_factor: f64,

    // === Order Rejection ===
    /// Enable random order rejection
    pub rejection_enabled: bool,
    /// Base probability of order rejection (0.0 - 1.0)
    pub rejection_base_probability: f64,
    /// Additional rejection probability during high volatility
    pub rejection_volatility_multiplier: f64,
}

impl Default for RealisticExecutionConfig {
    fn default() -> Self {
        Self {
            enabled: false,

            // Slippage: -0.1% to +0.2%, 70% chance of adverse
            slippage_min_pct: -0.001,
            slippage_max_pct: 0.002,
            slippage_adverse_probability: 0.7,

            // Spread: 0.05% base spread
            spread_enabled: true,
            spread_base_pct: 0.0005,
            spread_volatility_multiplier: 2.0,

            // Volume: max 2% of daily volume per order
            volume_limit_enabled: true,
            volume_participation_max_pct: 0.02,
            partial_fill_enabled: true,

            // Latency: execute on same bar (0) or next bar (1)
            latency_bars: 0,

            // Market impact: 0.1% price impact per 1% volume
            market_impact_enabled: true,
            market_impact_factor: 0.001,

            // Rejection: 0.5% base rejection rate
            rejection_enabled: false,
            rejection_base_probability: 0.005,
            rejection_volatility_multiplier: 2.0,
        }
    }
}

impl RealisticExecutionConfig {
    /// Preset for conservative/realistic simulation
    pub fn realistic() -> Self {
        Self {
            enabled: true,
            ..Default::default()
        }
    }

    /// Preset for aggressive/pessimistic simulation
    pub fn pessimistic() -> Self {
        Self {
            enabled: true,
            slippage_min_pct: 0.0,
            slippage_max_pct: 0.005,
            slippage_adverse_probability: 0.9,
            spread_base_pct: 0.001,
            spread_volatility_multiplier: 3.0,
            volume_participation_max_pct: 0.01,
            market_impact_factor: 0.002,
            rejection_enabled: true,
            rejection_base_probability: 0.01,
            ..Default::default()
        }
    }
}

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
    // Realistic execution simulation
    #[serde(default)]
    pub execution: RealisticExecutionConfig,
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
            execution: RealisticExecutionConfig::default(),
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
