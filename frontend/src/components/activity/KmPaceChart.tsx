import { useMemo } from 'react';
import {
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
} from 'recharts';
import type { ActivityLap } from '../../types/api';
import { formatPace } from '../../utils/format';

interface KmPaceChartProps {
  laps: ActivityLap[];
  className?: string;
}

// 페이스에 따른 색상 (빠를수록 시안, 느릴수록 빨강)
function getPaceColor(paceSeconds: number, avgPace: number): string {
  const diff = paceSeconds - avgPace;
  const ratio = Math.min(Math.abs(diff) / 30, 1); // 30초 차이를 기준으로 정규화

  if (diff < 0) {
    // 평균보다 빠름 - 시안 계열
    return `rgba(0, 212, 255, ${0.6 + ratio * 0.4})`;
  } else {
    // 평균보다 느림 - 주황/빨강 계열
    const r = Math.floor(255);
    const g = Math.floor(180 - ratio * 100);
    const b = Math.floor(100 - ratio * 60);
    return `rgb(${r}, ${g}, ${b})`;
  }
}

export function KmPaceChart({ laps, className = '' }: KmPaceChartProps) {
  // 가장 느린 페이스 계산 (막대 높이 기준점)
  const slowestPace = useMemo(() => {
    const paces = laps
      .filter((lap) => lap.distance_meters && lap.distance_meters >= 900 && lap.avg_pace_seconds)
      .map((lap) => lap.avg_pace_seconds!);
    return paces.length > 0 ? Math.max(...paces) + 15 : 0; // 15초 패딩
  }, [laps]);

  // 1km 단위 랩만 필터링 (마지막 랩은 제외 가능)
  const kmLaps = useMemo(() => {
    return laps
      .filter((lap) => lap.distance_meters && lap.distance_meters >= 900) // 900m 이상인 랩만
      .map((lap) => ({
        km: `${lap.lap_number}km`,
        kmNum: lap.lap_number,
        pace: lap.avg_pace_seconds || 0,
        paceFormatted: formatPace(lap.avg_pace_seconds),
        // barHeight: 느린 페이스에서 현재 페이스를 빼서, 빠를수록 높은 막대
        barHeight: slowestPace - (lap.avg_pace_seconds || slowestPace),
        hr: lap.avg_hr,
        elevation: lap.elevation_gain,
      }));
  }, [laps, slowestPace]);

  const avgPace = useMemo(() => {
    if (kmLaps.length === 0) return 0;
    return kmLaps.reduce((sum, lap) => sum + lap.pace, 0) / kmLaps.length;
  }, [kmLaps]);

  const avgHr = useMemo(() => {
    const lapsWithHr = kmLaps.filter((l) => l.hr != null);
    if (lapsWithHr.length === 0) return null;
    return Math.round(lapsWithHr.reduce((sum, lap) => sum + (lap.hr || 0), 0) / lapsWithHr.length);
  }, [kmLaps]);

  const hasHrData = kmLaps.some((l) => l.hr != null);

  if (kmLaps.length === 0) {
    return null;
  }

  // Y축 도메인 계산 (페이스) - 페이스는 낮을수록 빠름
  const minPace = Math.min(...kmLaps.map((l) => l.pace));
  const maxPace = Math.max(...kmLaps.map((l) => l.pace));
  const padding = 15; // 15초 패딩

  // 막대 높이 계산을 위한 기준점 (가장 느린 페이스 + 패딩)
  const baselinePace = maxPace + padding;

  // 심박수 도메인 계산
  const hrValues = kmLaps.filter((l) => l.hr != null).map((l) => l.hr!);
  const minHr = hrValues.length > 0 ? Math.min(...hrValues) - 5 : 100;
  const maxHr = hrValues.length > 0 ? Math.max(...hrValues) + 5 : 180;

  return (
    <div className={`card p-2 sm:p-3 ${className}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2 text-[10px] sm:text-xs text-muted">
          <span>
            평균 <span className="text-cyan font-mono">{formatPace(avgPace)}/km</span>
          </span>
          {avgHr && (
            <span>
              <span className="text-red-400 font-mono">{avgHr}</span> bpm
            </span>
          )}
        </div>
      </div>
      <div className="h-[200px] sm:h-[240px]">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={kmLaps}
            margin={{ top: 5, right: 5, left: 0, bottom: 20 }}
          >
            {/* km X축 (하단) */}
            <XAxis
              dataKey="kmNum"
              stroke="#484f58"
              fontSize={9}
              tickLine={false}
              axisLine={{ stroke: '#30363d' }}
              tickFormatter={(v) => `${v}`}
              interval={kmLaps.length > 20 ? Math.floor(kmLaps.length / 10) - 1 : 0}
            />
            {/* 페이스 Y축 (왼쪽) - 막대 높이용 (0 ~ max barHeight), 라벨은 페이스로 표시 */}
            <YAxis
              yAxisId="pace"
              domain={[0, baselinePace - minPace + padding]}
              stroke="#484f58"
              fontSize={9}
              tickFormatter={(v) => formatPace(baselinePace - v)}
              tickLine={false}
              axisLine={false}
              width={36}
              ticks={[0, (baselinePace - minPace) / 2, baselinePace - minPace]}
            />
            {/* 심박수 Y축 (오른쪽) */}
            {hasHrData && (
              <YAxis
                yAxisId="hr"
                orientation="right"
                domain={[minHr, maxHr]}
                stroke="#484f58"
                fontSize={9}
                tickLine={false}
                axisLine={false}
                width={28}
              />
            )}
            <Tooltip
              contentStyle={{
                background: '#1c2128',
                border: '1px solid #30363d',
                borderRadius: '8px',
                fontSize: '11px',
              }}
              formatter={(value, name, props) => {
                if (name === 'barHeight') {
                  // barHeight에서 실제 페이스 계산
                  const actualPace = props.payload.pace;
                  return [formatPace(actualPace) + '/km', '페이스'];
                }
                if (name === 'hr') {
                  return [value + ' bpm', '심박수'];
                }
                return [value, name];
              }}
              labelFormatter={(label) => `${label}km`}
            />
            <ReferenceLine
              yAxisId="pace"
              y={baselinePace - avgPace}
              stroke="#00d4ff"
              strokeDasharray="4 4"
              strokeOpacity={0.6}
            />
            <Bar yAxisId="pace" dataKey="barHeight" radius={[3, 3, 0, 0]} maxBarSize={24}>
              {kmLaps.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={getPaceColor(entry.pace, avgPace)} />
              ))}
            </Bar>
            {hasHrData && (
              <Line
                yAxisId="hr"
                type="monotone"
                dataKey="hr"
                stroke="#ff6b6b"
                strokeWidth={2}
                dot={{ fill: '#ff6b6b', strokeWidth: 0, r: 2 }}
                activeDot={{ r: 4, fill: '#ff6b6b' }}
              />
            )}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {/* Legend - compact */}
      <div className="flex items-center justify-center gap-3 mt-1 text-[9px] sm:text-[10px] text-muted">
        <div className="flex items-center gap-1">
          <div className="w-2.5 h-2.5 rounded" style={{ backgroundColor: 'rgba(0, 212, 255, 0.9)' }} />
          <span>빠름</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-2.5 h-2.5 rounded" style={{ backgroundColor: 'rgb(255, 140, 60)' }} />
          <span>느림</span>
        </div>
        {hasHrData && (
          <div className="flex items-center gap-1">
            <div className="w-4 border-t" style={{ borderColor: '#ff6b6b' }} />
            <span>HR</span>
          </div>
        )}
      </div>
    </div>
  );
}
