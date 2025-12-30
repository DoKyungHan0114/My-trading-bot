use std::fs::File;
use std::io::BufReader;
use std::path::Path;

use chrono::{DateTime, TimeZone, Utc};
use common::{BacktestError, Bar, Result};

/// Load bars from CSV file
pub fn load_csv(path: &Path) -> Result<Vec<Bar>> {
    let file = File::open(path).map_err(|e| BacktestError::DataLoadError(e.to_string()))?;
    let reader = BufReader::new(file);
    let mut csv_reader = csv::ReaderBuilder::new()
        .has_headers(true)
        .flexible(true)
        .from_reader(reader);

    let mut bars = Vec::new();

    for result in csv_reader.records() {
        let record = result.map_err(|e| BacktestError::CsvError(e.to_string()))?;

        // Expected columns: timestamp, open, high, low, close, volume, [vwap]
        if record.len() < 6 {
            continue;
        }

        let timestamp = parse_timestamp(&record[0])?;
        let open: f64 = record[1]
            .parse()
            .map_err(|_| BacktestError::CsvError("Invalid open price".to_string()))?;
        let high: f64 = record[2]
            .parse()
            .map_err(|_| BacktestError::CsvError("Invalid high price".to_string()))?;
        let low: f64 = record[3]
            .parse()
            .map_err(|_| BacktestError::CsvError("Invalid low price".to_string()))?;
        let close: f64 = record[4]
            .parse()
            .map_err(|_| BacktestError::CsvError("Invalid close price".to_string()))?;
        let volume: u64 = record[5]
            .parse()
            .map_err(|_| BacktestError::CsvError("Invalid volume".to_string()))?;

        let vwap = if record.len() > 6 {
            record[6].parse().ok()
        } else {
            None
        };

        bars.push(Bar {
            timestamp,
            open,
            high,
            low,
            close,
            volume,
            vwap,
        });
    }

    Ok(bars)
}

/// Load bars from JSON file
pub fn load_json(path: &Path) -> Result<Vec<Bar>> {
    let file = File::open(path).map_err(|e| BacktestError::DataLoadError(e.to_string()))?;
    let reader = BufReader::new(file);
    let bars: Vec<Bar> = serde_json::from_reader(reader)?;
    Ok(bars)
}

/// Parse timestamp from various formats
fn parse_timestamp(s: &str) -> Result<DateTime<Utc>> {
    // Try ISO 8601 format first
    if let Ok(dt) = DateTime::parse_from_rfc3339(s) {
        return Ok(dt.with_timezone(&Utc));
    }

    // Try common formats
    let formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%Y/%m/%d %H:%M:%S",
        "%Y/%m/%d",
    ];

    for fmt in &formats {
        if let Ok(dt) = chrono::NaiveDateTime::parse_from_str(s, fmt) {
            return Ok(Utc.from_utc_datetime(&dt));
        }
        if let Ok(date) = chrono::NaiveDate::parse_from_str(s, fmt) {
            return Ok(Utc
                .from_utc_datetime(&date.and_hms_opt(0, 0, 0).unwrap()));
        }
    }

    // Try Unix timestamp (seconds)
    if let Ok(ts) = s.parse::<i64>() {
        if let Some(dt) = DateTime::from_timestamp(ts, 0) {
            return Ok(dt);
        }
    }

    Err(BacktestError::CsvError(format!(
        "Unable to parse timestamp: {}",
        s
    )))
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{Datelike, Timelike};

    #[test]
    fn test_parse_timestamp_iso() {
        let ts = parse_timestamp("2024-01-15T09:30:00Z").unwrap();
        assert_eq!(ts.year(), 2024);
        assert_eq!(ts.month(), 1);
        assert_eq!(ts.day(), 15);
    }

    #[test]
    fn test_parse_timestamp_common() {
        let ts = parse_timestamp("2024-01-15 09:30:00").unwrap();
        assert_eq!(ts.year(), 2024);
    }

    #[test]
    fn test_parse_timestamp_date_only() {
        let ts = parse_timestamp("2024-01-15").unwrap();
        assert_eq!(ts.year(), 2024);
        assert_eq!(ts.hour(), 0);
    }

    #[test]
    fn test_parse_timestamp_unix() {
        let ts = parse_timestamp("1705312200").unwrap();
        assert!(ts.year() >= 2024);
    }
}
