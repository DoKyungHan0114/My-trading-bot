import { TrendingUp, TrendingDown } from 'lucide-react';
import type { Position } from '../types';

interface PositionCardProps {
  position: Position | null;
}

export function PositionCard({ position }: PositionCardProps) {
  if (!position) {
    return (
      <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Current Position</h3>
        <div className="flex items-center justify-center h-32 text-slate-400">
          No open position
        </div>
      </div>
    );
  }

  const isProfit = position.unrealized_pl >= 0;

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-lg font-semibold text-white mb-4">Current Position</h3>
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-2xl font-bold text-white">{position.symbol}</span>
            <span className="ml-2 text-slate-400">{position.qty} shares</span>
          </div>
          <div className={`flex items-center gap-1 px-3 py-1 rounded-full ${isProfit ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
            {isProfit ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
            <span className="font-medium">{isProfit ? '+' : ''}{position.unrealized_plpc.toFixed(2)}%</span>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-slate-400 text-sm">Entry Price</p>
            <p className="text-white font-medium">${position.avg_entry_price.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-slate-400 text-sm">Current Price</p>
            <p className="text-white font-medium">${position.current_price.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-slate-400 text-sm">Market Value</p>
            <p className="text-white font-medium">${position.market_value.toLocaleString()}</p>
          </div>
          <div>
            <p className="text-slate-400 text-sm">Unrealized P/L</p>
            <p className={`font-medium ${isProfit ? 'text-emerald-400' : 'text-red-400'}`}>
              {isProfit ? '+' : ''}${position.unrealized_pl.toFixed(2)}
            </p>
          </div>
        </div>

        <div className="pt-3 border-t border-slate-700">
          <p className="text-slate-400 text-sm">Entry Date</p>
          <p className="text-white">{new Date(position.entry_date).toLocaleDateString('ko-KR')}</p>
        </div>
      </div>
    </div>
  );
}
