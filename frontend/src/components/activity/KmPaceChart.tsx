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

// 랩 거리 패턴 감지 (1km 또는 400m 트랙)
function detectLapPattern(laps: ActivityLap[]): { unit: 'km' | 'track' | 'mixed'; minDistance: number; label: string } {
  const distances = laps
    .filter((lap) => lap.distance_meters && lap.distance_meters > 100)
    .map((lap) => lap.distance_meters!);

  if (distances.length === 0) return { unit: 'mixed', minDistance: 100, label: '' };

  // 평균 랩 거리 계산
  const avgDistance = distances.reduce((a, b) => a + b, 0) / distances.length;

  // 400m 트랙 패턴 감지 (350m ~ 450m)
  const trackLaps = distances.filter((d) => d >= 350 && d <= 450);
  if (trackLaps.length >= distances.length * 0.7) {
    return { unit: 'track', minDistance: 350, label: '400m' };
  }

  // 1km 랩 패턴 감지 (900m ~ 1100m)
  const filteredLaps = distances.filter((d) => d >= 900 && d <= 1100);
  if (filteredLaps.length >= distances.length * 0.7) {
    return { unit: 'km', minDistance: 900, label: 'km' };
  }

  // 혼합 패턴 - 가장 일반적인 패턴으로 필터링
  if (avgDistance >= 800) {
    return { unit: 'km', minDistance: 900, label: 'km' };
  } else if (avgDistance >= 300) {
    return { unit: 'track', minDistance: 350, label: '400m' };
  }

  return { unit: 'mixed', minDistance: 100, label: '' };
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
  // 랩 패턴 감지 (1km 또는 400m 트랙)
  const lapPattern = useMemo(() => detectLapPattern(laps), [laps]);

  // 가장 느린 페이스 계산 (막대 높이 기준점)
  const slowestPace = useMemo(() => {
    const paces = laps
      .filter((lap) => lap.distance_meters && lap.distance_meters >= lapPattern.minDistance && lap.avg_pace_seconds)
      .map((lap) => lap.avg_pace_seconds!);
    return paces.length > 0 ? Math.max(...paces) + 15 : 0; // 15초 패딩
  }, [laps, lapPattern.minDistance]);

  // 랩 필터링 (1km 또는 400m 트랙)
  const filteredLaps = useMemo(() => {
    return laps
      .filter((lap) => lap.distance_meters && lap.distance_meters >= lapPattern.minDistance)
      .map((lap) => ({
        km: lapPattern.unit === 'track' ? `${lap.lap_number}` : `${lap.lap_number}km`,
        kmNum: lap.lap_number,
        pace: lap.avg_pace_seconds || 0,
        paceFormatted: formatPace(lap.avg_pace_seconds),
        // barHeight: 느린 페이스에서 현재 페이스를 빼서, 빠를수록 높은 막대
        barHeight: slowestPace - (lap.avg_pace_seconds || slowestPace),
        hr: lap.avg_hr,
        elevation: lap.elevation_gain,
      }));
  }, [laps, slowestPace, lapPattern]);

  const avgPace = useMemo(() => {
    if (filteredLaps.length === 0) return 0;
    return filteredLaps.reduce((sum: number, lap) => sum + lap.pace, 0) / filteredLaps.length;
  }, [filteredLaps]);

  const avgHr = useMemo(() => {
    const lapsWithHr = filteredLaps.filter((l) => l.hr != null);
    if (lapsWithHr.length === 0) return null;
    return Math.round(lapsWithHr.reduce((sum: number, lap) => sum + (lap.hr || 0), 0) / lapsWithHr.length);
  }, [filteredLaps]);

  const hasHrData = filteredLaps.some((l) => l.hr != null);

  if (filteredLaps.length === 0) {
    return null;
  }

  // Y축 도메인 계산 (페이스) - 페이스는 낮을수록 빠름
  const minPace = Math.min(...filteredLaps.map((l) => l.pace));
  const maxPace = Math.max(...filteredLaps.map((l) => l.pace));
  const padding = 15; // 15초 패딩

  // 막대 높이 계산을 위한 기준점 (가장 느린 페이스 + 패딩)
  const baselinePace = maxPace + padding;

  // Y축 ticks를 15초 단위 라운드 페이스로 생성 (5:00, 5:15, 5:30 등)
  const paceTicks = useMemo(() => {
    const interval = 15; // 15초 단위
    // 가장 빠른 페이스를 15초 단위로 내림 (예: 293초 -> 285초 = 4:45)
    const roundedMinPace = Math.floor(minPace / interval) * interval;
    // 가장 느린 페이스를 15초 단위로 올림 (예: 347초 -> 360초 = 6:00)
    const roundedMaxPace = Math.ceil(maxPace / interval) * interval;

    const ticks: number[] = [];
    // 페이스 값에서 막대 높이로 변환 (baselinePace - pace)
    for (let pace = roundedMaxPace; pace >= roundedMinPace; pace -= interval) {
      const barHeight = baselinePace - pace;
      if (barHeight >= 0 && barHeight <= baselinePace - minPace + padding) {
        ticks.push(barHeight);
      }
    }
    return ticks;
  }, [minPace, maxPace, baselinePace, padding]);

  // 심박수 도메인 계산 - 평균 페이스와 평균 심박수가 같은 Y축 위치에 오도록 스케일 조정
  const hrValues = filteredLaps.filter((l) => l.hr != null).map((l) => l.hr!);
  const { alignedMinHr, alignedMaxHr } = useMemo(() => {
    if (hrValues.length === 0 || avgHr == null) {
      return { alignedMinHr: 100, alignedMaxHr: 180 };
    }

    // 페이스 Y축에서 평균 페이스의 상대적 위치 계산 (0~1 범위)
    const paceRange = baselinePace - minPace + padding;
    const avgPaceBarHeight = baselinePace - avgPace;
    const avgPaceRatio = avgPaceBarHeight / paceRange; // 평균 페이스의 Y축 비율

    // 심박수 범위 계산
    const actualMinHr = Math.min(...hrValues);
    const actualMaxHr = Math.max(...hrValues);
    const hrPadding = 5;

    // 평균 심박수가 avgPaceRatio 위치에 오도록 심박수 도메인 계산
    // avgPaceRatio = (avgHr - alignedMinHr) / (alignedMaxHr - alignedMinHr)
    // 심박수 범위를 페이스와 동일한 비율로 설정
    const hrAboveAvg = actualMaxHr - avgHr + hrPadding;
    const hrBelowAvg = avgHr - actualMinHr + hrPadding;

    // 평균이 avgPaceRatio 위치에 오려면:
    // hrBelowAvg / totalRange = avgPaceRatio
    // totalRange = hrBelowAvg / avgPaceRatio
    const totalRangeFromBelow = hrBelowAvg / avgPaceRatio;
    // 또는 hrAboveAvg / totalRange = (1 - avgPaceRatio)
    const totalRangeFromAbove = hrAboveAvg / (1 - avgPaceRatio);

    // 더 큰 범위를 사용해서 모든 데이터가 포함되도록
    const totalRange = Math.max(totalRangeFromBelow, totalRangeFromAbove);

    const newMinHr = avgHr - totalRange * avgPaceRatio;
    const newMaxHr = avgHr + totalRange * (1 - avgPaceRatio);

    return { alignedMinHr: Math.floor(newMinHr), alignedMaxHr: Math.ceil(newMaxHr) };
  }, [hrValues, avgHr, baselinePace, minPace, avgPace, padding]);

  return (
    <div className={`card p-1 sm:p-1.5 ${className}`}>
      <div className="flex items-center justify-between mb-0.5">
        <div className="flex items-center gap-2 text-[10px] sm:text-xs text-muted">
          {lapPattern.unit === 'track' && (
            <span className="px-1.5 py-0.5 bg-amber/20 text-amber rounded text-[9px]">트랙 400m</span>
          )}
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
            data={filteredLaps}
            margin={{ top: 5, right: 5, left: 0, bottom: 15 }}
          >
            {/* km X축 (하단) */}
            <XAxis
              dataKey="kmNum"
              stroke="#8b949e"
              tick={{ fill: '#8b949e' }}
              fontSize={10}
              tickLine={false}
              axisLine={{ stroke: '#484f58' }}
              tickFormatter={(v) => `${v}`}
              interval={filteredLaps.length > 20 ? Math.floor(filteredLaps.length / 10) - 1 : 0}
            />
            {/* 페이스 Y축 (왼쪽) - 막대 높이용 (0 ~ max barHeight), 라벨은 페이스로 표시 */}
            <YAxis
              yAxisId="pace"
              domain={[0, baselinePace - minPace + padding]}
              stroke="#8b949e"
              tick={{ fill: '#c9d1d9' }}
              fontSize={10}
              tickFormatter={(v) => formatPace(baselinePace - v)}
              tickLine={false}
              axisLine={false}
              width={40}
              ticks={paceTicks}
            />
            {/* 심박수 Y축 (오른쪽) - 평균이 페이스 평균과 같은 위치에 오도록 */}
            {hasHrData && (
              <YAxis
                yAxisId="hr"
                orientation="right"
                domain={[alignedMinHr, alignedMaxHr]}
                stroke="#8b949e"
                tick={{ fill: '#ff6b6b' }}
                fontSize={10}
                tickLine={false}
                axisLine={false}
                width={32}
              />
            )}
            <Tooltip
              contentStyle={{
                background: '#1c2128',
                border: '1px solid #30363d',
                borderRadius: '6px',
                fontSize: '12px',
                padding: '6px 10px',
              }}
              itemStyle={{ color: '#e6edf3', padding: 0, margin: 0 }}
              labelStyle={{ color: '#8b949e', fontWeight: 'bold', marginBottom: '2px' }}
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
              labelFormatter={(label) => lapPattern.unit === 'track' ? `Lap ${label}` : `${label}km`}
            />
            <ReferenceLine
              yAxisId="pace"
              y={baselinePace - avgPace}
              stroke="#00d4ff"
              strokeDasharray="4 4"
              strokeOpacity={0.6}
            />
            <Bar yAxisId="pace" dataKey="barHeight" radius={[3, 3, 0, 0]} maxBarSize={24}>
              {filteredLaps.map((entry, index) => (
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
      <div className="flex items-center justify-center gap-3 mt-0.5 text-[9px] sm:text-[10px] text-muted">
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
