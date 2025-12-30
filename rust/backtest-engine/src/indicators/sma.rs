/// Calculate Simple Moving Average
///
/// # Arguments
/// * `prices` - Slice of prices
/// * `period` - SMA period
///
/// # Returns
/// Vector of Option<f64>, None for values before enough data is available
pub fn calculate_sma(prices: &[f64], period: usize) -> Vec<Option<f64>> {
    let n = prices.len();
    let mut sma = vec![None; n];

    if n < period || period == 0 {
        return sma;
    }

    // Calculate initial sum
    let mut sum: f64 = prices[..period].iter().sum();
    sma[period - 1] = Some(sum / period as f64);

    // Sliding window for subsequent values
    for i in period..n {
        sum = sum - prices[i - period] + prices[i];
        sma[i] = Some(sum / period as f64);
    }

    sma
}

/// Calculate Simple Moving Average returning f64 with 0.0 for unavailable values
pub fn calculate_sma_filled(prices: &[f64], period: usize) -> Vec<f64> {
    calculate_sma(prices, period)
        .into_iter()
        .map(|v| v.unwrap_or(0.0))
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_sma_basic() {
        let prices = vec![1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0];
        let sma = calculate_sma(&prices, 3);

        assert_eq!(sma.len(), prices.len());
        assert!(sma[0].is_none());
        assert!(sma[1].is_none());
        assert_eq!(sma[2], Some(2.0)); // (1+2+3)/3
        assert_eq!(sma[3], Some(3.0)); // (2+3+4)/3
        assert_eq!(sma[9], Some(9.0)); // (8+9+10)/3
    }

    #[test]
    fn test_sma_period_larger_than_data() {
        let prices = vec![1.0, 2.0, 3.0];
        let sma = calculate_sma(&prices, 5);

        assert!(sma.iter().all(|v| v.is_none()));
    }

    #[test]
    fn test_sma_filled() {
        let prices = vec![1.0, 2.0, 3.0, 4.0, 5.0];
        let sma = calculate_sma_filled(&prices, 3);

        assert_eq!(sma[0], 0.0);
        assert_eq!(sma[1], 0.0);
        assert_eq!(sma[2], 2.0);
    }
}
