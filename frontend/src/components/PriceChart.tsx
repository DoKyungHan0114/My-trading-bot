import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import type { PriceData } from '../types';

interface PriceChartProps {
  data: PriceData[];
}

export function PriceChart({ data }: PriceChartProps) {
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-lg font-semibold text-white mb-4">TQQQ Price & Indicators</h3>
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis
              dataKey="timestamp"
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              tickFormatter={(value) => new Date(value).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
            />
            <YAxis
              yAxisId="price"
              orientation="right"
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              domain={['auto', 'auto']}
              tickFormatter={(value) => `$${value}`}
            />
            <YAxis
              yAxisId="volume"
              orientation="left"
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              tickFormatter={(value) => `${(value / 1000000).toFixed(0)}M`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#e2e8f0' }}
              formatter={(value, name) => {
                const v = Number(value);
                if (name === 'volume') return [`${(v / 1000000).toFixed(2)}M`, 'Volume'];
                if (name === 'close') return [`$${v.toFixed(2)}`, 'Close'];
                if (name === 'sma200') return [`$${v.toFixed(2)}`, 'SMA 200'];
                return [v, name];
              }}
            />
            <Bar
              yAxisId="volume"
              dataKey="volume"
              fill="#3b82f6"
              opacity={0.3}
            />
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="close"
              stroke="#22c55e"
              strokeWidth={2}
              dot={false}
            />
            <Line
              yAxisId="price"
              type="monotone"
              dataKey="sma200"
              stroke="#f59e0b"
              strokeWidth={1.5}
              strokeDasharray="5 5"
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

interface RSIChartProps {
  data: PriceData[];
}

export function RSIChart({ data }: RSIChartProps) {
  return (
    <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
      <h3 className="text-lg font-semibold text-white mb-4">RSI(2) Indicator</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            <XAxis
              dataKey="timestamp"
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              tickFormatter={(value) => new Date(value).toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' })}
            />
            <YAxis
              stroke="#64748b"
              tick={{ fill: '#94a3b8', fontSize: 11 }}
              domain={[0, 100]}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1e293b',
                border: '1px solid #334155',
                borderRadius: '8px',
              }}
              labelStyle={{ color: '#e2e8f0' }}
              formatter={(value) => [Number(value).toFixed(2), 'RSI(2)']}
            />
            <ReferenceLine y={70} stroke="#ef4444" strokeDasharray="3 3" label={{ value: '70', fill: '#ef4444', fontSize: 10 }} />
            <ReferenceLine y={10} stroke="#22c55e" strokeDasharray="3 3" label={{ value: '10', fill: '#22c55e', fontSize: 10 }} />
            <Line
              type="monotone"
              dataKey="rsi"
              stroke="#8b5cf6"
              strokeWidth={2}
              dot={false}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
