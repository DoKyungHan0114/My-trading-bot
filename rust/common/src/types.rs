use chrono::{DateTime, NaiveDate, Utc};
use serde::{Deserialize, Serialize};

/// OHLCV bar data
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Bar {
    pub timestamp: DateTime<Utc>,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: u64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vwap: Option<f64>,
}

impl Bar {
    pub fn new(
        timestamp: DateTime<Utc>,
        open: f64,
        high: f64,
        low: f64,
        close: f64,
        volume: u64,
    ) -> Self {
        Self {
            timestamp,
            open,
            high,
            low,
            close,
            volume,
            vwap: None,
        }
    }
}

/// Trade side
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Side {
    Buy,
    Sell,
    Short,
    Cover,
    HedgeBuy,
    HedgeSell,
}

/// Signal type
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum SignalType {
    Buy,
    Sell,
    Short,
    Cover,
    HedgeBuy,
    HedgeSell,
    Hold,
}

/// Trading signal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Signal {
    pub timestamp: DateTime<Utc>,
    pub signal_type: SignalType,
    pub symbol: String,
    pub price: f64,
    pub rsi: f64,
    pub reason: String,
    pub strength: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub vwap: Option<f64>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub sma: Option<f64>,
}

/// Position side
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum PositionSide {
    Long,
    Short,
    Hedge,
}

/// Position information
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Position {
    pub symbol: String,
    pub quantity: f64,
    pub avg_entry_price: f64,
    pub entry_date: DateTime<Utc>,
    pub current_price: f64,
    pub side: PositionSide,
    pub stop_loss_price: Option<f64>,
}

impl Position {
    pub fn unrealized_pnl(&self) -> f64 {
        let value_diff = self.current_price - self.avg_entry_price;
        match self.side {
            PositionSide::Long | PositionSide::Hedge => value_diff * self.quantity,
            PositionSide::Short => -value_diff * self.quantity,
        }
    }

    pub fn unrealized_pnl_pct(&self) -> f64 {
        let pnl = self.unrealized_pnl();
        let cost = self.avg_entry_price * self.quantity;
        if cost == 0.0 {
            0.0
        } else {
            (pnl / cost) * 100.0
        }
    }
}

/// Individual trade record
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trade {
    pub entry_date: DateTime<Utc>,
    pub entry_price: f64,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exit_date: Option<DateTime<Utc>>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub exit_price: Option<f64>,
    pub quantity: f64,
    pub side: Side,
    pub pnl: f64,
    pub pnl_pct: f64,
    pub holding_days: i64,
    pub entry_reason: String,
    pub exit_reason: String,
}

/// Performance metrics
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct PerformanceMetrics {
    // Returns
    pub total_return: f64,
    pub total_return_pct: f64,
    pub cagr: f64,
    // Risk metrics
    pub volatility: f64,
    pub sharpe_ratio: f64,
    pub sortino_ratio: f64,
    pub max_drawdown: f64,
    pub max_drawdown_duration_days: i64,
    pub calmar_ratio: f64,
    // Trade statistics
    pub total_trades: u32,
    pub winning_trades: u32,
    pub losing_trades: u32,
    pub win_rate: f64,
    pub avg_win: f64,
    pub avg_loss: f64,
    pub profit_factor: f64,
    pub expectancy: f64,
    pub avg_trade_duration_days: f64,
    pub best_trade: f64,
    pub worst_trade: f64,
    pub exposure_pct: f64,
}

/// Backtest result
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BacktestResult {
    pub metrics: PerformanceMetrics,
    pub equity_curve: Vec<(DateTime<Utc>, f64)>,
    pub drawdown_curve: Vec<(DateTime<Utc>, f64)>,
    pub trades: Vec<Trade>,
    pub start_date: NaiveDate,
    pub end_date: NaiveDate,
    pub initial_capital: f64,
    pub final_equity: f64,
    pub execution_time_ms: u64,
}
