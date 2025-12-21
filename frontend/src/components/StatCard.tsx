import type { LucideIcon } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  icon: LucideIcon;
  prefix?: string;
  suffix?: string;
}

export function StatCard({ title, value, change, icon: Icon, prefix = '', suffix = '' }: StatCardProps) {
  const isPositive = change !== undefined && change >= 0;

  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <div className="flex items-center justify-between mb-3">
        <span className="text-slate-400 text-sm font-medium">{title}</span>
        <Icon className="w-5 h-5 text-slate-500" />
      </div>
      <div className="flex items-end gap-2">
        <span className="text-2xl font-bold text-white">
          {prefix}{typeof value === 'number' ? value.toLocaleString() : value}{suffix}
        </span>
        {change !== undefined && (
          <span className={`text-sm font-medium ${isPositive ? 'text-emerald-400' : 'text-red-400'}`}>
            {isPositive ? '+' : ''}{change.toFixed(2)}%
          </span>
        )}
      </div>
    </div>
  );
}
