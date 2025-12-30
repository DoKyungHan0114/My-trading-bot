use chrono::{Duration, TimeZone, Utc};
use common::Bar;
use rand::Rng;

/// Generate synthetic TQQQ-like price data for testing
pub fn generate_synthetic_bars(days: usize, initial_price: f64) -> Vec<Bar> {
    let mut rng = rand::thread_rng();
    let mut bars = Vec::with_capacity(days);

    let mut price = initial_price;
    let start_date = Utc::now() - Duration::days(days as i64);

    // TQQQ-like parameters
    let daily_volatility = 0.03; // ~3% daily volatility (3x leveraged)
    let drift = 0.0001; // Slight upward drift

    for i in 0..days {
        let date = start_date + Duration::days(i as i64);

        // Generate daily return with mean-reverting tendency
        let random_return: f64 = rng.gen_range(-1.0..1.0);
        let daily_return = drift + daily_volatility * random_return;

        // Apply return
        let new_price = price * (1.0 + daily_return);

        // Generate OHLC
        let intraday_range = price * rng.gen_range(0.01..0.04);
        let open = price + rng.gen_range(-intraday_range / 2.0..intraday_range / 2.0);
        let close = new_price;

        let high = open.max(close) + rng.gen_range(0.0..intraday_range / 2.0);
        let low = open.min(close) - rng.gen_range(0.0..intraday_range / 2.0);

        // Generate volume (higher on volatile days)
        let base_volume = 50_000_000u64;
        let volume_multiplier = 1.0 + daily_return.abs() * 10.0;
        let volume = (base_volume as f64 * volume_multiplier * rng.gen_range(0.8..1.2)) as u64;

        // VWAP is typically between open and close
        let vwap = (open + close + high + low) / 4.0;

        bars.push(Bar {
            timestamp: date,
            open,
            high,
            low,
            close,
            volume,
            vwap: Some(vwap),
        });

        price = new_price;
    }

    bars
}

/// Generate bars with specific RSI characteristics for testing
pub fn generate_bars_with_rsi_pattern(
    days: usize,
    initial_price: f64,
    oversold_days: &[usize],
    overbought_days: &[usize],
) -> Vec<Bar> {
    let mut bars = Vec::with_capacity(days);
    let mut price = initial_price;
    let start_date = Utc::now() - Duration::days(days as i64);

    for i in 0..days {
        let date = start_date + Duration::days(i as i64);

        // Determine price movement based on RSI target
        let daily_return = if oversold_days.contains(&i) {
            -0.03 // Drop to trigger oversold
        } else if overbought_days.contains(&i) {
            0.03 // Rise to trigger overbought
        } else {
            0.001 // Slight drift
        };

        let new_price = price * (1.0 + daily_return);
        let range = price * 0.01;

        bars.push(Bar {
            timestamp: date,
            open: price,
            high: price.max(new_price) + range,
            low: price.min(new_price) - range,
            close: new_price,
            volume: 50_000_000,
            vwap: Some((price + new_price) / 2.0),
        });

        price = new_price;
    }

    bars
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_generate_synthetic_bars() {
        let bars = generate_synthetic_bars(100, 50.0);

        assert_eq!(bars.len(), 100);

        for bar in &bars {
            assert!(bar.high >= bar.low);
            assert!(bar.high >= bar.open);
            assert!(bar.high >= bar.close);
            assert!(bar.low <= bar.open);
            assert!(bar.low <= bar.close);
            assert!(bar.volume > 0);
        }
    }

    #[test]
    fn test_generate_pattern_bars() {
        let bars = generate_bars_with_rsi_pattern(50, 100.0, &[10, 11, 12], &[30, 31, 32]);

        assert_eq!(bars.len(), 50);

        // Verify drops on oversold days
        assert!(bars[12].close < bars[9].close);

        // Verify rises on overbought days
        assert!(bars[32].close > bars[29].close);
    }
}
