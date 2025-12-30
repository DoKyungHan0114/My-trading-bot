/// Calculate Exponential Moving Average
///
/// # Arguments
/// * `prices` - Slice of prices
/// * `period` - EMA period
///
/// # Returns
/// Vector of EMA values
pub fn calculate_ema(prices: &[f64], period: usize) -> Vec<f64> {
    let n = prices.len();
    if n == 0 || period == 0 {
        return vec![];
    }

    let mut ema = vec![0.0; n];
    let multiplier = 2.0 / (period as f64 + 1.0);

    // Initialize with first price
    ema[0] = prices[0];

    // Calculate EMA
    for i in 1..n {
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1];
    }

    ema
}

/// Calculate EMA with SMA as initial seed
///
/// This provides more accurate values at the beginning
pub fn calculate_ema_with_sma_seed(prices: &[f64], period: usize) -> Vec<f64> {
    let n = prices.len();
    if n < period || period == 0 {
        return vec![0.0; n];
    }

    let mut ema = vec![0.0; n];
    let multiplier = 2.0 / (period as f64 + 1.0);

    // Use SMA as initial seed
    let initial_sma: f64 = prices[..period].iter().sum::<f64>() / period as f64;
    ema[period - 1] = initial_sma;

    // Calculate EMA from period onwards
    for i in period..n {
        ema[i] = (prices[i] - ema[i - 1]) * multiplier + ema[i - 1];
    }

    ema
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ema_basic() {
        let prices = vec![10.0, 11.0, 12.0, 13.0, 14.0, 15.0];
        let ema = calculate_ema(&prices, 3);

        assert_eq!(ema.len(), prices.len());
        assert_eq!(ema[0], 10.0);
        // EMA should trend towards the price
        for i in 1..prices.len() {
            assert!(ema[i] > ema[i - 1]);
        }
    }

    #[test]
    fn test_ema_with_sma_seed() {
        let prices = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0];
        let ema = calculate_ema_with_sma_seed(&prices, 3);

        assert_eq!(ema.len(), prices.len());
        assert_eq!(ema[2], 2.0); // SMA of first 3 = (1+2+3)/3 = 2
    }

    #[test]
    fn test_ema_empty() {
        let prices: Vec<f64> = vec![];
        let ema = calculate_ema(&prices, 3);
        assert!(ema.is_empty());
    }
}
