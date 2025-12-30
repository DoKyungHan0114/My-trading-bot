/// Calculate RSI using Wilder's Smoothing (Exponential Moving Average)
///
/// # Arguments
/// * `prices` - Slice of closing prices
/// * `period` - RSI period (typically 2 for this strategy)
///
/// # Returns
/// Vector of RSI values (same length as input, with warmup period values set to 50.0)
pub fn calculate_rsi(prices: &[f64], period: usize) -> Vec<f64> {
    let n = prices.len();
    if n < period + 1 {
        return vec![50.0; n];
    }

    let mut rsi = vec![50.0; n];
    let alpha = 1.0 / period as f64;

    // Calculate initial averages
    let mut avg_gain = 0.0;
    let mut avg_loss = 0.0;

    for i in 1..=period {
        let delta = prices[i] - prices[i - 1];
        if delta > 0.0 {
            avg_gain += delta;
        } else {
            avg_loss += delta.abs();
        }
    }
    avg_gain /= period as f64;
    avg_loss /= period as f64;

    // Calculate first RSI
    if avg_loss == 0.0 {
        rsi[period] = 100.0;
    } else {
        let rs = avg_gain / avg_loss;
        rsi[period] = 100.0 - (100.0 / (1.0 + rs));
    }

    // Wilder's Smoothing for subsequent values
    for i in (period + 1)..n {
        let delta = prices[i] - prices[i - 1];
        let gain = if delta > 0.0 { delta } else { 0.0 };
        let loss = if delta < 0.0 { delta.abs() } else { 0.0 };

        avg_gain = avg_gain * (1.0 - alpha) + gain * alpha;
        avg_loss = avg_loss * (1.0 - alpha) + loss * alpha;

        if avg_loss == 0.0 {
            rsi[i] = 100.0;
        } else {
            let rs = avg_gain / avg_loss;
            rsi[i] = 100.0 - (100.0 / (1.0 + rs));
        }
    }

    rsi
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_rsi_basic() {
        let prices = vec![44.0, 44.25, 44.5, 43.75, 44.5, 44.25, 44.0, 43.5, 44.25, 44.5];
        let rsi = calculate_rsi(&prices, 2);

        assert_eq!(rsi.len(), prices.len());
        // First values should be default
        assert_eq!(rsi[0], 50.0);
        assert_eq!(rsi[1], 50.0);
        // RSI should be between 0 and 100
        for val in &rsi {
            assert!(*val >= 0.0 && *val <= 100.0);
        }
    }

    #[test]
    fn test_rsi_all_gains() {
        let prices = vec![10.0, 11.0, 12.0, 13.0, 14.0, 15.0];
        let rsi = calculate_rsi(&prices, 2);

        // All gains should result in RSI = 100
        assert_eq!(rsi[rsi.len() - 1], 100.0);
    }

    #[test]
    fn test_rsi_all_losses() {
        let prices = vec![15.0, 14.0, 13.0, 12.0, 11.0, 10.0];
        let rsi = calculate_rsi(&prices, 2);

        // All losses should result in RSI = 0
        assert_eq!(rsi[rsi.len() - 1], 0.0);
    }
}
