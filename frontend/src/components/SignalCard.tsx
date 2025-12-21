import type { Signal } from '../types';
import { ArrowUpCircle, ArrowDownCircle, MinusCircle } from 'lucide-react';

interface SignalCardProps {
  signal: Signal | null;
}

export function SignalCard({ signal }: SignalCardProps) {
  if (!signal) {
    return (
      <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
        <h3 className="text-lg font-semibold text-white mb-4">Latest Signal</h3>
        <div className="flex items-center justify-center h-32 text-slate-400">
          No signal available
        </div>
      </div>
    );
  }

  const getSignalConfig = () => {
    switch (signal.type) {
      case 'BUY':
        return {
          icon: ArrowUpCircle,
          color: 'text-emerald-400',
          bgColor: 'bg-emerald-500/20',
          borderColor: 'border-emerald-500/50',
        };
      case 'SELL':
        return {
          icon: ArrowDownCircle,
          color: 'text-red-400',
          bgColor: 'bg-red-500/20',
          borderColor: 'border-red-500/50',
        };
      default:
        return {
          icon: MinusCircle,
          color: 'text-slate-400',
          bgColor: 'bg-slate-500/20',
          borderColor: 'border-slate-500/50',
        };
    }
  };

  const config = getSignalConfig();
  const Icon = config.icon;

  return (
    <div className={`bg-slate-800 rounded-xl p-5 border ${config.borderColor}`}>
      <h3 className="text-lg font-semibold text-white mb-4">Latest Signal</h3>
      <div className="space-y-4">
        <div className="flex items-center gap-3">
          <div className={`p-3 rounded-full ${config.bgColor}`}>
            <Icon className={`w-8 h-8 ${config.color}`} />
          </div>
          <div>
            <p className={`text-2xl font-bold ${config.color}`}>{signal.type}</p>
            <p className="text-slate-400 text-sm">
              {new Date(signal.timestamp).toLocaleString('ko-KR')}
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-slate-400 text-sm">Price</p>
            <p className="text-white font-medium">${signal.price.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-slate-400 text-sm">RSI(2)</p>
            <p className={`font-medium ${signal.rsi <= 10 ? 'text-emerald-400' : signal.rsi >= 70 ? 'text-red-400' : 'text-white'}`}>
              {signal.rsi.toFixed(2)}
            </p>
          </div>
          <div>
            <p className="text-slate-400 text-sm">SMA 200</p>
            <p className="text-white font-medium">${signal.sma200.toFixed(2)}</p>
          </div>
          <div>
            <p className="text-slate-400 text-sm">Strength</p>
            <div className="flex items-center gap-2">
              <div className="flex-1 h-2 bg-slate-700 rounded-full overflow-hidden">
                <div
                  className={`h-full ${config.bgColor.replace('/20', '')}`}
                  style={{ width: `${signal.strength * 100}%` }}
                />
              </div>
              <span className="text-white text-sm">{(signal.strength * 100).toFixed(0)}%</span>
            </div>
          </div>
        </div>

        <div className="pt-3 border-t border-slate-700">
          <p className="text-slate-400 text-sm">Reason</p>
          <p className="text-white">{signal.reason}</p>
        </div>
      </div>
    </div>
  );
}
