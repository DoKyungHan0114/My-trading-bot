import type { Trade } from '../types';
import { ArrowUpRight, ArrowDownRight } from 'lucide-react';

interface TradeHistoryProps {
  trades: Trade[];
}

export function TradeHistory({ trades }: TradeHistoryProps) {
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-lg font-semibold text-white mb-4">Recent Trades</h3>
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="text-left text-slate-400 text-sm border-b border-slate-700">
              <th className="pb-3 font-medium">Date</th>
              <th className="pb-3 font-medium">Side</th>
              <th className="pb-3 font-medium">Qty</th>
              <th className="pb-3 font-medium">Price</th>
              <th className="pb-3 font-medium">Total</th>
              <th className="pb-3 font-medium text-right">P/L</th>
            </tr>
          </thead>
          <tbody>
            {trades.length === 0 ? (
              <tr>
                <td colSpan={6} className="py-8 text-center text-slate-400">
                  No trades yet
                </td>
              </tr>
            ) : (
              trades.map((trade) => (
                <tr key={trade.id} className="border-b border-slate-700/50 hover:bg-slate-700/30">
                  <td className="py-3 text-slate-300">
                    {new Date(trade.timestamp).toLocaleDateString('ko-KR')}
                  </td>
                  <td className="py-3">
                    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                      trade.side === 'buy'
                        ? 'bg-emerald-500/20 text-emerald-400'
                        : 'bg-red-500/20 text-red-400'
                    }`}>
                      {trade.side === 'buy' ? (
                        <ArrowUpRight className="w-3 h-3" />
                      ) : (
                        <ArrowDownRight className="w-3 h-3" />
                      )}
                      {trade.side.toUpperCase()}
                    </span>
                  </td>
                  <td className="py-3 text-white">{trade.qty}</td>
                  <td className="py-3 text-white">${trade.price.toFixed(2)}</td>
                  <td className="py-3 text-white">${trade.total.toLocaleString()}</td>
                  <td className="py-3 text-right">
                    {trade.pnl !== undefined ? (
                      <span className={trade.pnl >= 0 ? 'text-emerald-400' : 'text-red-400'}>
                        {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)}
                        <span className="text-xs ml-1">
                          ({trade.pnl_percent?.toFixed(2)}%)
                        </span>
                      </span>
                    ) : (
                      <span className="text-slate-500">-</span>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
