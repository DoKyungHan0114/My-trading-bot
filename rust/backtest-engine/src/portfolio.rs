use chrono::{DateTime, Utc};
use common::{Position, PositionSide, Result, Side, Trade};

/// Portfolio manager for tracking positions and calculating P&L
#[derive(Debug)]
pub struct Portfolio {
    initial_capital: f64,
    cash: f64,
    position: Option<Position>,
    hedge_position: Option<Position>,
    realized_pnl: f64,
    trades: Vec<Trade>,
}

impl Portfolio {
    pub fn new(initial_capital: f64) -> Self {
        Self {
            initial_capital,
            cash: initial_capital,
            position: None,
            hedge_position: None,
            realized_pnl: 0.0,
            trades: Vec::new(),
        }
    }

    /// Get current equity (cash + position value)
    pub fn equity(&self) -> f64 {
        self.cash + self.position_value() + self.hedge_position_value()
    }

    /// Get position market value
    pub fn position_value(&self) -> f64 {
        self.position
            .as_ref()
            .map(|p| p.quantity * p.current_price)
            .unwrap_or(0.0)
    }

    /// Get hedge position market value
    pub fn hedge_position_value(&self) -> f64 {
        self.hedge_position
            .as_ref()
            .map(|p| p.quantity * p.current_price)
            .unwrap_or(0.0)
    }

    /// Get available cash
    pub fn cash(&self) -> f64 {
        self.cash
    }

    /// Check if there's an open position
    pub fn has_position(&self) -> bool {
        self.position.is_some()
    }

    /// Check if there's a hedge position
    pub fn has_hedge_position(&self) -> bool {
        self.hedge_position.is_some()
    }

    /// Get current position reference
    pub fn current_position(&self) -> Option<&Position> {
        self.position.as_ref()
    }

    /// Get current hedge position reference
    pub fn current_hedge_position(&self) -> Option<&Position> {
        self.hedge_position.as_ref()
    }

    /// Get all closed trades
    pub fn trades(&self) -> &[Trade] {
        &self.trades
    }

    /// Get realized P&L
    pub fn realized_pnl(&self) -> f64 {
        self.realized_pnl
    }

    /// Update current prices for positions
    pub fn update_prices(&mut self, main_price: f64, hedge_price: Option<f64>) {
        if let Some(pos) = self.position.as_mut() {
            pos.current_price = main_price;
        }
        if let Some(pos) = self.hedge_position.as_mut() {
            if let Some(price) = hedge_price {
                pos.current_price = price;
            }
        }
    }

    /// Open a new position
    pub fn open_position(
        &mut self,
        symbol: &str,
        quantity: f64,
        price: f64,
        side: PositionSide,
        timestamp: DateTime<Utc>,
        stop_loss_price: Option<f64>,
        commission: f64,
    ) -> Result<()> {
        let cost = quantity * price + commission;

        if cost > self.cash {
            return Err(common::BacktestError::InsufficientCash {
                required: cost,
                available: self.cash,
            });
        }

        self.cash -= cost;

        let position = Position {
            symbol: symbol.to_string(),
            quantity,
            avg_entry_price: price,
            entry_date: timestamp,
            current_price: price,
            side,
            stop_loss_price,
        };

        match side {
            PositionSide::Hedge => {
                self.hedge_position = Some(position);
            }
            _ => {
                self.position = Some(position);
            }
        }

        Ok(())
    }

    /// Close current position
    pub fn close_position(
        &mut self,
        price: f64,
        timestamp: DateTime<Utc>,
        reason: &str,
        commission: f64,
    ) -> Option<Trade> {
        let position = self.position.take()?;
        self.close_position_internal(position, price, timestamp, reason, commission)
    }

    /// Close hedge position
    pub fn close_hedge_position(
        &mut self,
        price: f64,
        timestamp: DateTime<Utc>,
        reason: &str,
        commission: f64,
    ) -> Option<Trade> {
        let position = self.hedge_position.take()?;
        self.close_position_internal(position, price, timestamp, reason, commission)
    }

    fn close_position_internal(
        &mut self,
        position: Position,
        price: f64,
        timestamp: DateTime<Utc>,
        reason: &str,
        commission: f64,
    ) -> Option<Trade> {
        let proceeds = position.quantity * price - commission;
        let cost_basis = position.quantity * position.avg_entry_price;

        let pnl = match position.side {
            PositionSide::Short => cost_basis - proceeds,
            _ => proceeds - cost_basis,
        };

        self.cash += proceeds;
        self.realized_pnl += pnl;

        let exit_side = match position.side {
            PositionSide::Long => Side::Sell,
            PositionSide::Short => Side::Cover,
            PositionSide::Hedge => Side::HedgeSell,
        };

        let holding_days = (timestamp - position.entry_date).num_days();

        let trade = Trade {
            entry_date: position.entry_date,
            entry_price: position.avg_entry_price,
            exit_date: Some(timestamp),
            exit_price: Some(price),
            quantity: position.quantity,
            side: exit_side,
            pnl,
            pnl_pct: if cost_basis > 0.0 {
                (pnl / cost_basis) * 100.0
            } else {
                0.0
            },
            holding_days,
            entry_reason: String::new(),
            exit_reason: reason.to_string(),
        };

        self.trades.push(trade.clone());
        Some(trade)
    }

    /// Check if stop loss is triggered
    pub fn check_stop_loss(&self, current_price: f64) -> bool {
        if let Some(pos) = &self.position {
            if let Some(stop_price) = pos.stop_loss_price {
                match pos.side {
                    PositionSide::Long => current_price <= stop_price,
                    PositionSide::Short => current_price >= stop_price,
                    _ => false,
                }
            } else {
                false
            }
        } else {
            false
        }
    }

    /// Calculate position size based on available capital
    pub fn calculate_position_size(
        &self,
        price: f64,
        position_size_pct: f64,
        cash_reserve_pct: f64,
    ) -> f64 {
        let available = self.cash * (1.0 - cash_reserve_pct);
        let target_value = available * position_size_pct;
        (target_value / price).floor()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use chrono::TimeZone;

    fn now() -> DateTime<Utc> {
        Utc.with_ymd_and_hms(2024, 1, 1, 12, 0, 0).unwrap()
    }

    #[test]
    fn test_portfolio_new() {
        let portfolio = Portfolio::new(10000.0);
        assert_eq!(portfolio.equity(), 10000.0);
        assert_eq!(portfolio.cash(), 10000.0);
        assert!(!portfolio.has_position());
    }

    #[test]
    fn test_open_and_close_position() {
        let mut portfolio = Portfolio::new(10000.0);

        // Open position
        portfolio
            .open_position("TQQQ", 100.0, 50.0, PositionSide::Long, now(), None, 0.0)
            .unwrap();

        assert!(portfolio.has_position());
        assert_eq!(portfolio.cash(), 5000.0);
        assert_eq!(portfolio.position_value(), 5000.0);
        assert_eq!(portfolio.equity(), 10000.0);

        // Update price
        portfolio.update_prices(55.0, None);
        assert_eq!(portfolio.position_value(), 5500.0);
        assert_eq!(portfolio.equity(), 10500.0);

        // Close position
        let trade = portfolio
            .close_position(55.0, now(), "take profit", 0.0)
            .unwrap();

        assert!(!portfolio.has_position());
        assert_eq!(portfolio.cash(), 10500.0);
        assert_eq!(trade.pnl, 500.0);
        assert_eq!(trade.pnl_pct, 10.0);
    }

    #[test]
    fn test_insufficient_cash() {
        let mut portfolio = Portfolio::new(1000.0);

        let result = portfolio.open_position(
            "TQQQ",
            100.0,
            50.0,
            PositionSide::Long,
            now(),
            None,
            0.0,
        );

        assert!(result.is_err());
    }

    #[test]
    fn test_stop_loss() {
        let mut portfolio = Portfolio::new(10000.0);

        portfolio
            .open_position(
                "TQQQ",
                100.0,
                50.0,
                PositionSide::Long,
                now(),
                Some(47.5), // 5% stop loss
                0.0,
            )
            .unwrap();

        assert!(!portfolio.check_stop_loss(48.0));
        assert!(portfolio.check_stop_loss(47.0));
    }

    #[test]
    fn test_calculate_position_size() {
        let portfolio = Portfolio::new(10000.0);

        // 90% position size, 10% cash reserve
        let size = portfolio.calculate_position_size(50.0, 0.9, 0.1);
        // Available: 10000 * 0.9 = 9000
        // Target: 9000 * 0.9 = 8100
        // Shares: 8100 / 50 = 162
        assert_eq!(size, 162.0);
    }
}
