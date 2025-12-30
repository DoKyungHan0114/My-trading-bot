/// Calculate Average True Range
///
/// # Arguments
/// * `highs` - Slice of high prices
/// * `lows` - Slice of low prices
/// * `closes` - Slice of closing prices
/// * `period` - ATR period (typically 14)
///
/// # Returns
/// Vector of ATR values
pub fn calculate_atr(highs: &[f64], lows: &[f64], closes: &[f64], period: usize) -> Vec<f64> {
    let n = highs.len();
    if n < 2 || period == 0 {
        return vec![0.0; n];
    }

    let mut atr = vec![0.0; n];
    let alpha = 1.0 / period as f64;

    // Calculate True Range
    let mut tr = vec![0.0; n];
    tr[0] = highs[0] - lows[0];

    for i in 1..n {
        let hl = highs[i] - lows[i];
        let hc = (highs[i] - closes[i - 1]).abs();
        let lc = (lows[i] - closes[i - 1]).abs();
        tr[i] = hl.max(hc).max(lc);
    }

    // Calculate initial ATR as SMA of first 'period' TR values
    if n >= period {
        atr[period - 1] = tr[..period].iter().sum::<f64>() / period as f64;

        // Wilder's Smoothing for subsequent values
        for i in period..n {
            atr[i] = atr[i - 1] * (1.0 - alpha) + tr[i] * alpha;
        }
    }

    atr
}

/// Calculate True Range for a single bar
pub fn true_range(high: f64, low: f64, prev_close: f64) -> f64 {
    let hl = high - low;
    let hc = (high - prev_close).abs();
    let lc = (low - prev_close).abs();
    hl.max(hc).max(lc)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_atr_basic() {
        let highs = vec![48.7, 48.72, 48.9, 48.87, 48.82, 49.05, 49.2, 49.35, 49.92, 50.19];
        let lows = vec![47.79, 48.14, 48.39, 48.37, 48.24, 48.64, 48.94, 48.86, 49.5, 49.87];
        let closes = vec![48.16, 48.61, 48.75, 48.63, 48.74, 49.03, 49.07, 49.32, 49.91, 50.13];

        let atr = calculate_atr(&highs, &lows, &closes, 5);

        assert_eq!(atr.len(), highs.len());
        // ATR should be positive
        for i in 4..atr.len() {
            assert!(atr[i] > 0.0);
        }
    }

    #[test]
    fn test_true_range() {
        let tr = true_range(50.0, 48.0, 49.0);
        // TR should be max(50-48, |50-49|, |48-49|) = max(2, 1, 1) = 2
        assert_eq!(tr, 2.0);
    }

    #[test]
    fn test_true_range_gap_up() {
        // Gap up scenario
        let tr = true_range(52.0, 51.0, 48.0);
        // TR should be max(52-51, |52-48|, |51-48|) = max(1, 4, 3) = 4
        assert_eq!(tr, 4.0);
    }
}
