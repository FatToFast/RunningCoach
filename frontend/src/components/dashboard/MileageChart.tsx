import { useRef, useState, useEffect } from 'react';
import { BarChart, Bar, XAxis, YAxis, Tooltip, Cell } from 'recharts';

interface MileageData {
  label: string;
  distance: number;
  isCurrent?: boolean;
}

interface MileageChartProps {
  data: MileageData[];
  period: 'week' | 'month';
}

export function MileageChart({ data, period }: MileageChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [dimensions, setDimensions] = useState({ width: 300, height: 160 });

  useEffect(() => {
    const updateDimensions = () => {
      if (containerRef.current) {
        const { width, height } = containerRef.current.getBoundingClientRect();
        if (width > 0 && height > 0) {
          setDimensions({ width, height });
        }
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, []);

  const maxDistance = Math.max(...data.map((d) => d.distance), 1);

  if (data.length === 0) {
    return (
      <div className="card p-3 sm:p-4">
        <h3 className="font-display text-sm font-semibold text-muted uppercase tracking-wider mb-3">
          {period === 'week' ? '주간' : '월간'} 마일리지
        </h3>
        <div className="h-[160px] flex items-center justify-center text-muted text-sm">
          데이터가 없습니다
        </div>
      </div>
    );
  }

  return (
    <div className="card p-3 sm:p-4">
      <h3 className="font-display text-sm font-semibold text-muted uppercase tracking-wider mb-3">
        {period === 'week' ? '주간' : '월간'} 마일리지
      </h3>
      <div ref={containerRef} className="h-[160px] sm:h-[200px]">
        <BarChart
          width={dimensions.width}
          height={dimensions.height}
          data={data}
          margin={{ top: 5, right: 5, left: 0, bottom: 5 }}
        >
          <XAxis
            dataKey="label"
            stroke="var(--color-text-muted)"
            fontSize={10}
            tickLine={false}
            axisLine={{ stroke: 'var(--color-border)' }}
          />
          <YAxis
            stroke="var(--color-text-muted)"
            fontSize={10}
            tickLine={false}
            axisLine={false}
            width={32}
            tickFormatter={(v) => `${v}`}
            domain={[0, Math.ceil(maxDistance * 1.1)]}
          />
          <Tooltip
            contentStyle={{
              background: 'var(--color-bg-elevated)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              fontSize: '12px',
            }}
            formatter={(value) => [`${Number(value).toFixed(1)} km`, '거리']}
            labelFormatter={(label) => label}
          />
          <Bar dataKey="distance" radius={[4, 4, 0, 0]} maxBarSize={40}>
            {data.map((entry, index) => (
              <Cell
                key={`cell-${index}`}
                fill={entry.isCurrent ? 'var(--color-accent)' : 'var(--color-accent-muted)'}
              />
            ))}
          </Bar>
        </BarChart>
      </div>
    </div>
  );
}
