import type { SystemStatus as Status } from '../types';
import { Activity, Power, Clock, Building2 } from 'lucide-react';

interface SystemStatusProps {
  status: Status;
}

export function SystemStatus({ status }: SystemStatusProps) {
  return (
    <div className="bg-slate-800 rounded-xl p-4 border border-slate-700">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <Power className={`w-4 h-4 ${status.is_running ? 'text-emerald-400' : 'text-red-400'}`} />
            <span className={`text-sm font-medium ${status.is_running ? 'text-emerald-400' : 'text-red-400'}`}>
              {status.is_running ? 'Running' : 'Stopped'}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-slate-400" />
            <span className={`text-sm font-medium px-2 py-0.5 rounded ${
              status.mode === 'live'
                ? 'bg-red-500/20 text-red-400'
                : status.mode === 'paper'
                ? 'bg-amber-500/20 text-amber-400'
                : 'bg-blue-500/20 text-blue-400'
            }`}>
              {status.mode.toUpperCase()} MODE
            </span>
          </div>

          <div className="flex items-center gap-2">
            <Building2 className={`w-4 h-4 ${status.market_open ? 'text-emerald-400' : 'text-slate-400'}`} />
            <span className={`text-sm ${status.market_open ? 'text-emerald-400' : 'text-slate-400'}`}>
              Market {status.market_open ? 'Open' : 'Closed'}
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2 text-slate-400">
          <Clock className="w-4 h-4" />
          <span className="text-sm">
            Last update: {new Date(status.last_update).toLocaleTimeString('ko-KR')}
          </span>
        </div>
      </div>
    </div>
  );
}
