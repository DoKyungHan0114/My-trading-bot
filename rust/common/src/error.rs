use thiserror::Error;

#[derive(Error, Debug)]
pub enum BacktestError {
    #[error("Insufficient data: need at least {required} bars, got {actual}")]
    InsufficientData { required: usize, actual: usize },

    #[error("Insufficient cash: need ${required:.2}, have ${available:.2}")]
    InsufficientCash { required: f64, available: f64 },

    #[error("No position to close")]
    NoPositionToClose,

    #[error("Position already exists for {symbol}")]
    PositionAlreadyExists { symbol: String },

    #[error("Invalid parameter: {0}")]
    InvalidParameter(String),

    #[error("Data loading error: {0}")]
    DataLoadError(String),

    #[error("IO error: {0}")]
    IoError(#[from] std::io::Error),

    #[error("CSV parse error: {0}")]
    CsvError(String),

    #[error("JSON error: {0}")]
    JsonError(#[from] serde_json::Error),
}

pub type Result<T> = std::result::Result<T, BacktestError>;
