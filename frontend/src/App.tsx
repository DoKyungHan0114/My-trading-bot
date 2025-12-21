import { useState, useEffect } from 'react';
import { Wallet, TrendingUp, DollarSign, BarChart3, RefreshCw } from 'lucide-react';
import { StatCard } from './components/StatCard';
import { PriceChart, RSIChart } from './components/PriceChart';
import { PositionCard } from './components/PositionCard';
import { SignalCard } from './components/SignalCard';
import { TradeHistory } from './components/TradeHistory';
import { SystemStatus } from './components/SystemStatus';
import { EquityCurve } from './components/EquityCurve';
import type { AccountInfo, Position, Signal, Trade, PriceData, SystemStatus as SystemStatusType } from './types';
import './index.css';

// Mock data for demonstration
const mockAccount: AccountInfo = {
  equity: 12450.32,
  cash: 1245.03,
  buying_power: 2490.06,
  portfolio_value: 11205.29,
  daily_pnl: 234.56,
  daily_pnl_percent: 1.92,
};

const mockPosition: Position = {
  symbol: 'TQQQ',
  qty: 150,
  avg_entry_price: 72.45,
  current_price: 74.70,
  market_value: 11205.00,
  unrealized_pl: 337.50,
  unrealized_plpc: 3.11,
  entry_date: '2024-12-15T14:30:00Z',
};

const mockSignal: Signal = {
  timestamp: new Date().toISOString(),
  type: 'HOLD',
  price: 74.70,
  rsi: 45.32,
  sma200: 68.25,
  reason: 'RSI in neutral zone, holding current position',
  strength: 0.65,
};

const mockTrades: Trade[] = [
  { id: '1', timestamp: '2024-12-15T14:30:00Z', side: 'buy', symbol: 'TQQQ', qty: 150, price: 72.45, total: 10867.50 },
  { id: '2', timestamp: '2024-12-10T15:45:00Z', side: 'sell', symbol: 'TQQQ', qty: 120, price: 71.20, total: 8544.00, pnl: 432.00, pnl_percent: 5.33 },
  { id: '3', timestamp: '2024-12-05T10:15:00Z', side: 'buy', symbol: 'TQQQ', qty: 120, price: 67.60, total: 8112.00 },
  { id: '4', timestamp: '2024-11-28T14:00:00Z', side: 'sell', symbol: 'TQQQ', qty: 100, price: 69.80, total: 6980.00, pnl: 280.00, pnl_percent: 4.18 },
  { id: '5', timestamp: '2024-11-20T09:30:00Z', side: 'buy', symbol: 'TQQQ', qty: 100, price: 67.00, total: 6700.00 },
];

const mockStatus: SystemStatusType = {
  mode: 'paper',
  is_running: true,
  last_update: new Date().toISOString(),
  market_open: false,
};

// Generate mock price data
const generatePriceData = (): PriceData[] => {
  const data: PriceData[] = [];
  let price = 65;
  const now = new Date();

  for (let i = 60; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);

    const change = (Math.random() - 0.48) * 3;
    price = Math.max(50, Math.min(85, price + change));

    const high = price + Math.random() * 2;
    const low = price - Math.random() * 2;
    const open = low + Math.random() * (high - low);

    data.push({
      timestamp: date.toISOString(),
      open,
      high,
      low,
      close: price,
      volume: Math.floor(Math.random() * 50000000) + 10000000,
      rsi: Math.min(100, Math.max(0, 50 + (Math.random() - 0.5) * 60)),
      sma200: 68 + (i - 30) * 0.05,
    });
  }

  return data;
};

// Generate mock equity curve
const generateEquityCurve = () => {
  const data = [];
  let equity = 10000;
  const now = new Date();

  for (let i = 90; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);

    const change = (Math.random() - 0.45) * 200;
    equity = Math.max(8000, equity + change);

    data.push({
      date: date.toISOString(),
      equity: Math.round(equity * 100) / 100,
    });
  }

  return data;
};

function App() {
  const [account, setAccount] = useState<AccountInfo>(mockAccount);
  const [position] = useState<Position | null>(mockPosition);
  const [signal] = useState<Signal | null>(mockSignal);
  const [trades] = useState<Trade[]>(mockTrades);
  const [status, setStatus] = useState<SystemStatusType>(mockStatus);
  const [priceData] = useState<PriceData[]>(generatePriceData());
  const [equityCurve] = useState(generateEquityCurve());
  const [loading, setLoading] = useState(false);

  const fetchData = async () => {
    setLoading(true);
    try {
      const response = await fetch('/api/dashboard');
      if (response.ok) {
        const data = await response.json();
        setAccount(data.account);
        setStatus(data.status);
      } else {
        // Fallback to mock data variations
        setAccount({
          ...mockAccount,
          daily_pnl: mockAccount.daily_pnl + (Math.random() - 0.5) * 50,
          daily_pnl_percent: mockAccount.daily_pnl_percent + (Math.random() - 0.5) * 0.5,
        });
        setStatus({
          ...status,
          last_update: new Date().toISOString(),
        });
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      // Fallback to mock data
      setStatus({
        ...status,
        last_update: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Refresh data every 60 seconds
    const interval = setInterval(fetchData, 60000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="min-h-screen bg-slate-900 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-white">TQQQ Trading Dashboard</h1>
            <p className="text-slate-400 mt-1">RSI(2) Mean Reversion Strategy</p>
          </div>
          <button
            onClick={fetchData}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* System Status */}
        <SystemStatus status={status} />

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Equity"
            value={account.equity.toFixed(2)}
            change={account.daily_pnl_percent}
            icon={Wallet}
            prefix="$"
          />
          <StatCard
            title="Cash Available"
            value={account.cash.toFixed(2)}
            icon={DollarSign}
            prefix="$"
          />
          <StatCard
            title="Portfolio Value"
            value={account.portfolio_value.toFixed(2)}
            icon={TrendingUp}
            prefix="$"
          />
          <StatCard
            title="Daily P/L"
            value={account.daily_pnl.toFixed(2)}
            change={account.daily_pnl_percent}
            icon={BarChart3}
            prefix={account.daily_pnl >= 0 ? '+$' : '-$'}
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PriceChart data={priceData} />
          <EquityCurve data={equityCurve} />
        </div>

        {/* RSI Chart */}
        <RSIChart data={priceData} />

        {/* Position and Signal */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <PositionCard position={position} />
          <SignalCard signal={signal} />
        </div>

        {/* Trade History */}
        <TradeHistory trades={trades} />

        {/* Footer */}
        <div className="text-center text-slate-500 text-sm py-4">
          TQQQ Trading System v1.0 | Paper Trading Mode
        </div>
      </div>
    </div>
  );
}

export default App;
