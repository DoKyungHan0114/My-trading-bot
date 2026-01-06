//! Realistic order execution simulator
//!
//! Simulates real-world trading conditions including:
//! - Random slippage with adverse probability bias
//! - Bid/ask spread modeling
//! - Volume-based fill constraints
//! - Order latency (bar delay)
//! - Market impact for large orders
//! - Random order rejection

use common::{Bar, RealisticExecutionConfig, Side};
use rand::Rng;

/// Result of an execution attempt
#[derive(Debug, Clone)]
pub struct ExecutionResult {
    /// Whether the order was executed
    pub executed: bool,
    /// Final execution price (after slippage, spread, impact)
    pub fill_price: f64,
    /// Quantity actually filled (may be less due to volume constraints)
    pub fill_quantity: f64,
    /// Original requested quantity
    pub requested_quantity: f64,
    /// Breakdown of price adjustments
    pub price_adjustments: PriceAdjustments,
    /// Reason if order was rejected or partially filled
    pub notes: Vec<String>,
}

/// Breakdown of price adjustments applied
#[derive(Debug, Clone, Default)]
pub struct PriceAdjustments {
    pub base_price: f64,
    pub slippage: f64,
    pub spread: f64,
    pub market_impact: f64,
    pub total_adjustment: f64,
}

/// Pending order waiting for execution (for latency simulation)
#[derive(Debug, Clone)]
pub struct PendingOrder {
    pub symbol: String,
    pub side: Side,
    pub quantity: f64,
    pub signal_bar_index: usize,
    pub execute_at_bar_index: usize,
}

/// Execution simulator with realistic market conditions
pub struct ExecutionSimulator {
    config: RealisticExecutionConfig,
    pending_orders: Vec<PendingOrder>,
    rng: rand::rngs::ThreadRng,
}

impl ExecutionSimulator {
    pub fn new(config: RealisticExecutionConfig) -> Self {
        Self {
            config,
            pending_orders: Vec::new(),
            rng: rand::thread_rng(),
        }
    }

    /// Check if realistic execution is enabled
    pub fn is_enabled(&self) -> bool {
        self.config.enabled
    }

    /// Calculate execution price with all adjustments
    pub fn simulate_execution(
        &mut self,
        bar: &Bar,
        side: Side,
        quantity: f64,
        volatility: Option<f64>,
    ) -> ExecutionResult {
        if !self.config.enabled {
            // If disabled, return simple execution at close price
            return ExecutionResult {
                executed: true,
                fill_price: bar.close,
                fill_quantity: quantity,
                requested_quantity: quantity,
                price_adjustments: PriceAdjustments {
                    base_price: bar.close,
                    ..Default::default()
                },
                notes: vec![],
            };
        }

        let mut notes = Vec::new();
        let volatility = volatility.unwrap_or(0.02); // Default 2% volatility

        // 1. Check for order rejection
        if self.should_reject_order(volatility) {
            return ExecutionResult {
                executed: false,
                fill_price: 0.0,
                fill_quantity: 0.0,
                requested_quantity: quantity,
                price_adjustments: Default::default(),
                notes: vec!["Order rejected due to market conditions".to_string()],
            };
        }

        // 2. Calculate fill quantity (volume constraints)
        let fill_quantity = self.calculate_fill_quantity(bar, quantity, &mut notes);
        if fill_quantity <= 0.0 {
            return ExecutionResult {
                executed: false,
                fill_price: 0.0,
                fill_quantity: 0.0,
                requested_quantity: quantity,
                price_adjustments: Default::default(),
                notes,
            };
        }

        // 3. Calculate base price (can use VWAP or close)
        let base_price = bar.vwap.unwrap_or(bar.close);

        // 4. Calculate all price adjustments
        let slippage = self.calculate_slippage(base_price, side);
        let spread = self.calculate_spread(base_price, side, volatility);
        let market_impact =
            self.calculate_market_impact(base_price, side, fill_quantity, bar.volume);

        let total_adjustment = slippage + spread + market_impact;
        let fill_price = base_price + total_adjustment;

        // Ensure price stays within bar's high/low range
        let fill_price = fill_price.max(bar.low).min(bar.high);

        ExecutionResult {
            executed: true,
            fill_price,
            fill_quantity,
            requested_quantity: quantity,
            price_adjustments: PriceAdjustments {
                base_price,
                slippage,
                spread,
                market_impact,
                total_adjustment,
            },
            notes,
        }
    }

    /// Calculate slippage with adverse probability bias
    fn calculate_slippage(&mut self, price: f64, side: Side) -> f64 {
        let is_adverse = self.rng.gen::<f64>() < self.config.slippage_adverse_probability;

        let slippage_pct = if is_adverse {
            // Adverse slippage (unfavorable direction)
            let max = self.config.slippage_max_pct.abs();
            if max > 0.0 {
                self.rng.gen_range(0.0..max)
            } else {
                0.0
            }
        } else {
            // Favorable slippage (can be 0 if min is 0)
            let min = self.config.slippage_min_pct;
            if min < 0.0 {
                self.rng.gen_range(min..0.0)
            } else {
                0.0
            }
        };

        let slippage = price * slippage_pct;

        // For buys, adverse means higher price; for sells, adverse means lower price
        match side {
            Side::Buy | Side::HedgeBuy | Side::Cover => slippage,
            Side::Sell | Side::HedgeSell | Side::Short => -slippage,
        }
    }

    /// Calculate spread cost based on side and volatility
    fn calculate_spread(&mut self, price: f64, side: Side, volatility: f64) -> f64 {
        if !self.config.spread_enabled {
            return 0.0;
        }

        // Spread widens with volatility
        let volatility_factor = 1.0 + (volatility * self.config.spread_volatility_multiplier);
        let half_spread = price * self.config.spread_base_pct * volatility_factor;

        // Buys pay the ask (higher), sells receive bid (lower)
        match side {
            Side::Buy | Side::HedgeBuy | Side::Cover => half_spread,
            Side::Sell | Side::HedgeSell | Side::Short => -half_spread,
        }
    }

    /// Calculate market impact for large orders
    fn calculate_market_impact(
        &self,
        price: f64,
        side: Side,
        quantity: f64,
        bar_volume: u64,
    ) -> f64 {
        if !self.config.market_impact_enabled || bar_volume == 0 {
            return 0.0;
        }

        // Calculate what percentage of daily volume this order represents
        let order_value = quantity * price;
        let avg_trade_value = price * (bar_volume as f64 / 100.0); // Assume ~100 trades per bar
        let volume_participation = order_value / (bar_volume as f64 * price);

        // Impact increases quadratically with participation rate
        let impact_pct = self.config.market_impact_factor * volume_participation.powi(2) * 100.0;
        let impact = price * impact_pct;

        // Buys push price up, sells push price down
        match side {
            Side::Buy | Side::HedgeBuy | Side::Cover => impact,
            Side::Sell | Side::HedgeSell | Side::Short => -impact,
        }
    }

    /// Calculate actual fill quantity based on volume constraints
    fn calculate_fill_quantity(&self, bar: &Bar, quantity: f64, notes: &mut Vec<String>) -> f64 {
        if !self.config.volume_limit_enabled {
            return quantity;
        }

        let max_quantity_by_volume =
            (bar.volume as f64) * self.config.volume_participation_max_pct / bar.close;

        if quantity <= max_quantity_by_volume {
            return quantity;
        }

        if self.config.partial_fill_enabled {
            notes.push(format!(
                "Partial fill: {:.2} of {:.2} shares due to volume constraints",
                max_quantity_by_volume, quantity
            ));
            max_quantity_by_volume.floor().max(0.0)
        } else {
            notes.push("Order rejected: exceeds volume participation limit".to_string());
            0.0
        }
    }

    /// Check if order should be rejected
    fn should_reject_order(&mut self, volatility: f64) -> bool {
        if !self.config.rejection_enabled {
            return false;
        }

        let rejection_prob = self.config.rejection_base_probability
            + (volatility * self.config.rejection_volatility_multiplier);

        self.rng.gen::<f64>() < rejection_prob
    }

    // === Latency Simulation ===

    /// Queue an order for delayed execution
    pub fn queue_order(
        &mut self,
        symbol: String,
        side: Side,
        quantity: f64,
        current_bar_index: usize,
    ) {
        let execute_at = current_bar_index + self.config.latency_bars;
        self.pending_orders.push(PendingOrder {
            symbol,
            side,
            quantity,
            signal_bar_index: current_bar_index,
            execute_at_bar_index: execute_at,
        });
    }

    /// Get orders ready to execute at current bar
    pub fn get_executable_orders(&mut self, current_bar_index: usize) -> Vec<PendingOrder> {
        let (ready, pending): (Vec<_>, Vec<_>) = self
            .pending_orders
            .drain(..)
            .partition(|o| o.execute_at_bar_index <= current_bar_index);

        self.pending_orders = pending;
        ready
    }

    /// Check if there's latency (orders need to be queued)
    pub fn has_latency(&self) -> bool {
        self.config.enabled && self.config.latency_bars > 0
    }

    /// Get pending order count
    pub fn pending_order_count(&self) -> usize {
        self.pending_orders.len()
    }

    /// Clear all pending orders
    pub fn clear_pending_orders(&mut self) {
        self.pending_orders.clear();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::{TimeZone, Utc};

    fn sample_bar(close: f64, volume: u64) -> Bar {
        Bar {
            timestamp: Utc.with_ymd_and_hms(2024, 1, 1, 12, 0, 0).unwrap(),
            open: close - 0.5,
            high: close + 1.0,
            low: close - 1.0,
            close,
            volume,
            vwap: Some(close + 0.1),
        }
    }

    #[test]
    fn test_disabled_simulator() {
        let config = RealisticExecutionConfig::default(); // disabled by default
        let mut sim = ExecutionSimulator::new(config);

        let bar = sample_bar(100.0, 1_000_000);
        let result = sim.simulate_execution(&bar, Side::Buy, 100.0, None);

        assert!(result.executed);
        assert_eq!(result.fill_price, 100.0);
        assert_eq!(result.fill_quantity, 100.0);
    }

    #[test]
    fn test_enabled_simulator_applies_adjustments() {
        let config = RealisticExecutionConfig::realistic();
        let mut sim = ExecutionSimulator::new(config);

        let bar = sample_bar(100.0, 1_000_000);
        let result = sim.simulate_execution(&bar, Side::Buy, 100.0, None);

        assert!(result.executed);
        // Price should be adjusted (likely higher for buy due to slippage/spread)
        assert_ne!(result.fill_price, bar.close);
        assert!(result.fill_price >= bar.low && result.fill_price <= bar.high);
    }

    #[test]
    fn test_volume_constraint_partial_fill() {
        let mut config = RealisticExecutionConfig::realistic();
        config.volume_participation_max_pct = 0.01; // 1% max
        config.partial_fill_enabled = true;

        let mut sim = ExecutionSimulator::new(config);

        // Try to buy more than 1% of volume
        let bar = sample_bar(100.0, 100_000); // 100k shares
        let result = sim.simulate_execution(&bar, Side::Buy, 2000.0, None); // 2k shares = 2%

        assert!(result.executed);
        assert!(result.fill_quantity < result.requested_quantity);
        assert!(result.notes.iter().any(|n| n.contains("Partial fill")));
    }

    #[test]
    fn test_latency_queue() {
        let mut config = RealisticExecutionConfig::realistic();
        config.latency_bars = 1;

        let mut sim = ExecutionSimulator::new(config);

        // Queue order at bar 0
        sim.queue_order("TQQQ".to_string(), Side::Buy, 100.0, 0);
        assert_eq!(sim.pending_order_count(), 1);

        // Check at bar 0 - should not be ready
        let ready = sim.get_executable_orders(0);
        assert!(ready.is_empty());
        assert_eq!(sim.pending_order_count(), 1);

        // Check at bar 1 - should be ready
        let ready = sim.get_executable_orders(1);
        assert_eq!(ready.len(), 1);
        assert_eq!(sim.pending_order_count(), 0);
    }

    #[test]
    fn test_slippage_direction() {
        let mut config = RealisticExecutionConfig::realistic();
        config.slippage_adverse_probability = 1.0; // Always adverse
        config.spread_enabled = false;
        config.market_impact_enabled = false;

        let mut sim = ExecutionSimulator::new(config);
        let bar = sample_bar(100.0, 1_000_000);

        // Buy should have positive slippage (higher price)
        let buy_result = sim.simulate_execution(&bar, Side::Buy, 100.0, None);
        assert!(buy_result.price_adjustments.slippage >= 0.0);

        // Sell should have negative slippage (lower price)
        let sell_result = sim.simulate_execution(&bar, Side::Sell, 100.0, None);
        assert!(sell_result.price_adjustments.slippage <= 0.0);
    }
}
