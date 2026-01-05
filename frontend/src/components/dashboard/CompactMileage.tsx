import { useMemo } from 'react';
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Cell, Tooltip } from 'recharts';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import clsx from 'clsx';

interface MileageData {
  label: string;
  distance: number;
  isCurrent?: boolean;
}

interface CompactMileageProps {
  data: MileageData[];
  period: 'week' | 'month';
}

export function CompactMileage({ data, period }: CompactMileageProps) {
  const stats = useMemo(() => {
    if (data.length < 2) return null;

    const currentIdx = data.findIndex(d => d.isCurrent);
    const current = data[currentIdx]?.distance ?? 0;
    const previous = data[currentIdx - 1]?.distance ?? 0;
    const avg = data.slice(0, -1).reduce((sum, d) => sum + d.distance, 0) / Math.max(data.length - 1, 1);

    const changePercent = previous > 0 ? ((current - previous) / previous) * 100 : 0;
    const vsAvgPercent = avg > 0 ? ((current - avg) / avg) * 100 : 0;

    return {
      current,
      previous,
      avg,
      changePercent,
      vsAvgPercent,
    };
  }, [data]);

  if (data.length === 0) {
    return (
      <div className="card p-3">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-muted uppercase tracking-wider">
            {period === 'week' ? '주간' : '월간'} 마일리지
          </span>
        </div>
        <div className="h-20 flex items-center justify-center text-muted text-xs">
          데이터가 없습니다
        </div>
      </div>
    );
  }

  const maxDistance = Math.max(...data.map(d => d.distance), 1);

  return (
    <div className="card p-3">
      {/* Header with stats */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-muted uppercase tracking-wider">
            {period === 'week' ? '주간' : '월간'} 마일리지
          </span>
          {stats && (
            <div className="flex items-center gap-1">
              {stats.changePercent > 5 ? (
                <TrendingUp className="w-3 h-3 text-positive" />
              ) : stats.changePercent < -5 ? (
                <TrendingDown className="w-3 h-3 text-danger" />
              ) : (
                <Minus className="w-3 h-3 text-muted" />
              )}
              <span className={clsx(
                'text-[10px] font-mono',
                stats.changePercent > 5 ? 'text-positive' :
                stats.changePercent < -5 ? 'text-danger' : 'text-muted'
              )}>
                {stats.changePercent > 0 ? '+' : ''}{stats.changePercent.toFixed(0)}%
              </span>
            </div>
          )}
        </div>
        {stats && (
          <div className="text-right">
            <span className="font-mono text-lg font-semibold text-accent">
              {stats.current.toFixed(1)}
            </span>
            <span className="text-[10px] text-muted ml-0.5">km</span>
          </div>
        )}
      </div>

      {/* Bar Chart - 높이 증가 */}
      <div className="h-32">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 5, right: 5, left: 0, bottom: 0 }}>
            <XAxis
              dataKey="label"
              stroke="var(--color-text-muted)"
              fontSize={10}
              tickLine={false}
              axisLine={{ stroke: 'var(--color-border)' }}
              interval={0}
              tick={{ dy: 5 }}
            />
            <YAxis
              stroke="var(--color-text-muted)"
              fontSize={9}
              tickLine={false}
              axisLine={false}
              width={28}
              tickFormatter={(v) => `${v}`}
              domain={[0, Math.ceil(maxDistance * 1.1)]}
            />
            <Tooltip
              contentStyle={{
                background: 'var(--color-bg-elevated)',
                border: '1px solid var(--color-border)',
                borderRadius: '6px',
                fontSize: '11px',
                padding: '6px 10px',
              }}
              formatter={(value) => [`${Number(value).toFixed(1)} km`, '거리']}
              labelFormatter={(label) => label}
            />
            <Bar dataKey="distance" radius={[4, 4, 0, 0]} maxBarSize={32}>
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.isCurrent ? 'var(--color-accent)' : 'var(--color-accent-muted)'}
                  opacity={entry.isCurrent ? 1 : 0.5}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Quick stats row */}
      {stats && (
        <div className="flex items-center justify-between mt-2 pt-2 border-t border-[var(--color-border)] text-[10px]">
          <div className="text-muted">
            이전: <span className="font-mono text-secondary">{stats.previous.toFixed(1)}km</span>
          </div>
          <div className="text-muted">
            평균: <span className="font-mono text-secondary">{stats.avg.toFixed(1)}km</span>
          </div>
          <div className={clsx(
            'font-mono',
            stats.vsAvgPercent >= 0 ? 'text-positive' : 'text-warning'
          )}>
            vs평균 {stats.vsAvgPercent >= 0 ? '+' : ''}{stats.vsAvgPercent.toFixed(0)}%
          </div>
        </div>
      )}
    </div>
  );
}
