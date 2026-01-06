pub mod data;
pub mod engine;
pub mod execution;
pub mod indicators;
pub mod metrics;
pub mod portfolio;
pub mod signals;

pub use data::{generate_synthetic_bars, load_file};
pub use engine::BacktestEngine;
pub use execution::{ExecutionResult, ExecutionSimulator, PriceAdjustments};
pub use metrics::MetricsCalculator;
pub use portfolio::Portfolio;
pub use signals::SignalGenerator;

// Re-export common types
pub use common::{
    BacktestError, BacktestParameters, BacktestResult, Bar, PerformanceMetrics, Position,
    PositionSide, Result, Side, Signal, SignalType, Trade,
};
