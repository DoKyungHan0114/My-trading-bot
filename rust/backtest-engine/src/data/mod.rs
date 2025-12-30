pub mod loader;
pub mod synthetic;

pub use loader::{load_csv, load_json};
pub use synthetic::{generate_bars_with_rsi_pattern, generate_synthetic_bars};

use std::path::Path;

use common::{BacktestError, Bar, Result};

/// Load bars from file, detecting format from extension
pub fn load_file(path: &Path) -> Result<Vec<Bar>> {
    let ext = path
        .extension()
        .and_then(|e| e.to_str())
        .unwrap_or("")
        .to_lowercase();

    match ext.as_str() {
        "csv" => load_csv(path),
        "json" => load_json(path),
        _ => Err(BacktestError::DataLoadError(format!(
            "Unsupported file format: {}",
            ext
        ))),
    }
}
