export interface AccountInfo {
  equity: number;
  cash: number;
  buying_power: number;
  portfolio_value: number;
  daily_pnl: number;
  daily_pnl_percent: number;
}

export interface Position {
  symbol: string;
  qty: number;
  avg_entry_price: number;
  current_price: number;
  market_value: number;
  unrealized_pl: number;
  unrealized_plpc: number;
  entry_date: string;
}

export interface Signal {
  timestamp: string;
  type: 'BUY' | 'SELL' | 'HOLD';
  price: number;
  rsi: number;
  sma200: number;
  reason: string;
  strength: number;
}

export interface Trade {
  id: string;
  timestamp: string;
  side: 'buy' | 'sell';
  symbol: string;
  qty: number;
  price: number;
  total: number;
  pnl?: number;
  pnl_percent?: number;
}

export interface PriceData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  rsi?: number;
  sma200?: number;
}

export interface BacktestResult {
  total_return: number;
  sharpe_ratio: number;
  max_drawdown: number;
  win_rate: number;
  total_trades: number;
  profit_factor: number;
  equity_curve: { date: string; equity: number }[];
}

export interface SystemStatus {
  mode: 'paper' | 'live' | 'backtest';
  is_running: boolean;
  last_update: string;
  market_open: boolean;
}
