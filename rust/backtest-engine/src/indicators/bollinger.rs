/// Bollinger Bands result
#[derive(Debug, Clone)]
pub struct BollingerBands {
    pub upper: Vec<f64>,
    pub middle: Vec<f64>,
    pub lower: Vec<f64>,
}

/// Calculate Bollinger Bands
///
/// # Arguments
/// * `prices` - Slice of closing prices
/// * `period` - Period for moving average (typically 20)
/// * `std_dev` - Number of standard deviations (typically 2.0)
///
/// # Returns
/// BollingerBands struct containing upper, middle (SMA), and lower bands
pub fn calculate_bollinger_bands(prices: &[f64], period: usize, std_dev: f64) -> BollingerBands {
    let n = prices.len();
    let mut bb = BollingerBands {
        upper: vec![0.0; n],
        middle: vec![0.0; n],
        lower: vec![0.0; n],
    };

    if n < period || period == 0 {
        return bb;
    }

    for i in (period - 1)..n {
        let start = i + 1 - period;
        let window = &prices[start..=i];

        // Calculate mean
        let mean: f64 = window.iter().sum::<f64>() / period as f64;

        // Calculate standard deviation
        let variance: f64 = window.iter().map(|x| (x - mean).powi(2)).sum::<f64>() / period as f64;
        let std = variance.sqrt();

        bb.middle[i] = mean;
        bb.upper[i] = mean + std * std_dev;
        bb.lower[i] = mean - std * std_dev;
    }

    bb
}

/// Check if price is above upper band
pub fn is_above_upper(price: f64, upper: f64) -> bool {
    price > upper
}

/// Check if price is below lower band
pub fn is_below_lower(price: f64, lower: f64) -> bool {
    price < lower
}

/// Calculate %B indicator (position within bands)
/// Returns value between 0 and 1 when within bands
/// < 0 means below lower band, > 1 means above upper band
pub fn percent_b(price: f64, lower: f64, upper: f64) -> f64 {
    if upper == lower {
        return 0.5;
    }
    (price - lower) / (upper - lower)
}

/// Calculate bandwidth (volatility indicator)
pub fn bandwidth(upper: f64, middle: f64, lower: f64) -> f64 {
    if middle == 0.0 {
        return 0.0;
    }
    (upper - lower) / middle
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bollinger_bands_basic() {
        let prices = vec![
            22.27, 22.19, 22.08, 22.17, 22.18, 22.13, 22.23, 22.43, 22.24, 22.29, 22.15, 22.39,
            22.38, 22.61, 23.36, 24.05, 23.75, 23.83, 23.95, 23.63,
        ];
        let bb = calculate_bollinger_bands(&prices, 20, 2.0);

        assert_eq!(bb.middle.len(), prices.len());

        // The 20th value (index 19) should be valid
        assert!(bb.middle[19] > 0.0);
        assert!(bb.upper[19] > bb.middle[19]);
        assert!(bb.lower[19] < bb.middle[19]);
    }

    #[test]
    fn test_percent_b() {
        let lower = 100.0;
        let upper = 110.0;

        assert_eq!(percent_b(100.0, lower, upper), 0.0);
        assert_eq!(percent_b(105.0, lower, upper), 0.5);
        assert_eq!(percent_b(110.0, lower, upper), 1.0);
        assert!(percent_b(95.0, lower, upper) < 0.0);
        assert!(percent_b(115.0, lower, upper) > 1.0);
    }

    #[test]
    fn test_bandwidth() {
        let bw = bandwidth(110.0, 100.0, 90.0);
        assert_eq!(bw, 0.2); // (110-90)/100 = 0.2
    }
}
