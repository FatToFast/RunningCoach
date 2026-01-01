/**
 * 공통 포맷팅 유틸리티
 * 날짜, 시간, 페이스, 거리 등 일관된 형식으로 표시
 */

// 날짜 문자열을 안전하게 Date 객체로 변환
// - ISO 8601 형식 지원 (타임존 포함/미포함)
// - Invalid Date 체크
function parseDate(dateStr: string | Date): Date | null {
  if (dateStr instanceof Date) {
    return isNaN(dateStr.getTime()) ? null : dateStr;
  }
  const date = new Date(dateStr);
  return isNaN(date.getTime()) ? null : date;
}

// 로컬 날짜만 비교 (시간 제외)
function isSameLocalDate(date1: Date, date2: Date): boolean {
  return (
    date1.getFullYear() === date2.getFullYear() &&
    date1.getMonth() === date2.getMonth() &&
    date1.getDate() === date2.getDate()
  );
}

// 페이스 포맷 (초 → mm:ss)
export function formatPace(seconds: number | null | undefined): string {
  if (seconds == null) return '--:--';
  // Math.round로 전체 초를 반올림한 후 분/초 계산 (60초 오버플로우 방지)
  const totalSeconds = Math.round(seconds);
  const min = Math.floor(totalSeconds / 60);
  const sec = totalSeconds % 60;
  return `${min}:${String(sec).padStart(2, '0')}`;
}

// 지속시간 포맷 (초 → hh:mm:ss 또는 mm:ss)
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '--:--';
  // Math.round로 전체 초를 반올림한 후 시/분/초 계산 (60초 오버플로우 방지)
  const totalSeconds = Math.round(seconds);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
  }
  return `${minutes}:${String(secs).padStart(2, '0')}`;
}

// 지속시간 간결 포맷 (초 → Xh Ym 또는 Xm)
export function formatDurationCompact(seconds: number | null | undefined): string {
  if (seconds == null) return '--';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}시간 ${minutes}분`;
  }
  return `${minutes}분`;
}

// 거리 포맷 (미터 → km)
export function formatDistance(meters: number | null | undefined): string {
  if (meters == null) return '--';
  const km = meters / 1000;
  return km.toFixed(2);
}

// 거리 포맷 간결 (미터 → X.X km)
export function formatDistanceCompact(meters: number | null | undefined): string {
  if (meters == null) return '--';
  const km = meters / 1000;
  return `${km.toFixed(1)} km`;
}

// 날짜 포맷 (한국어)
export function formatDate(dateStr: string | Date): string {
  const date = parseDate(dateStr);
  if (!date) return '--';

  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (isSameLocalDate(date, today)) {
    return '오늘';
  }
  if (isSameLocalDate(date, yesterday)) {
    return '어제';
  }

  return date.toLocaleDateString('ko-KR', { month: 'short', day: 'numeric' });
}

// 날짜 전체 포맷 (한국어)
export function formatDateFull(dateStr: string | Date): string {
  const date = parseDate(dateStr);
  if (!date) return '--';
  return date.toLocaleDateString('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  });
}

// 시간 포맷 (HH:mm)
export function formatTime(dateStr: string | Date): string {
  const date = parseDate(dateStr);
  if (!date) return '--:--';
  return date.toLocaleTimeString('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  });
}

// 캐시된 Intl.DateTimeFormat 인스턴스 (성능 최적화)
const dateTimeFormatters = {
  full: new Intl.DateTimeFormat('ko-KR', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    weekday: 'long',
  }),
  time: new Intl.DateTimeFormat('ko-KR', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }),
};

// 날짜+시간 포맷 (최적화: 한 번의 파싱으로 모든 형식 생성)
export function formatDateTime(dateStr: string | Date): { date: string; time: string; full: string } {
  const date = parseDate(dateStr);
  if (!date) {
    return { date: '--', time: '--:--', full: '--' };
  }
  const dateFormatted = dateTimeFormatters.full.format(date);
  const timeFormatted = dateTimeFormatters.time.format(date);
  return {
    date: dateFormatted,
    time: timeFormatted,
    full: `${dateFormatted} ${timeFormatted}`,
  };
}

// 심박수 포맷
export function formatHeartRate(hr: number | null | undefined): string {
  if (hr == null) return '--';
  return `${Math.round(hr)}`;
}

// 칼로리 포맷
export function formatCalories(cal: number | null | undefined): string {
  if (cal == null) return '--';
  return cal.toLocaleString('ko-KR');
}

// 고도 포맷
export function formatElevation(meters: number | null | undefined): string {
  if (meters == null) return '--';
  return `${Math.round(meters)}m`;
}

// 케이던스 포맷
export function formatCadence(spm: number | null | undefined): string {
  if (spm == null) return '--';
  return `${Math.round(spm)}`;
}

// 속도 포맷 (m/s → km/h)
export function formatSpeed(mps: number | null | undefined): string {
  if (mps == null) return '--';
  const kmh = mps * 3.6;
  return `${kmh.toFixed(1)}`;
}

// 소수점 페이스 → mm:ss 변환 (차트용)
export function formatPaceFromDecimal(paceDecimal: number): string {
  // 전체 초로 변환 후 반올림하여 60초 오버플로우 방지
  const totalSeconds = Math.round(paceDecimal * 60);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

// 페이스 존 분류
export function getPaceZone(paceSeconds: number | null): { label: string; labelKo: string; color: string } {
  if (paceSeconds == null) return { label: 'N/A', labelKo: '없음', color: 'text-gray-400' };

  if (paceSeconds < 270) return { label: 'Speed', labelKo: '스피드', color: 'text-red-400' };
  if (paceSeconds < 300) return { label: 'Tempo', labelKo: '템포', color: 'text-amber' };
  if (paceSeconds < 360) return { label: 'Steady', labelKo: '안정', color: 'text-green-400' };
  return { label: 'Easy', labelKo: '이지', color: 'text-cyan' };
}

// 활동 타입 색상
export function getActivityTypeColor(type: string): string {
  switch (type) {
    case 'running':
      return 'text-cyan';
    case 'cycling':
      return 'text-green-400';
    case 'swimming':
      return 'text-blue-400';
    default:
      return 'text-gray-400';
  }
}

// 활동 타입 한국어
export function getActivityTypeLabel(type: string): string {
  switch (type) {
    case 'running':
      return '러닝';
    case 'cycling':
      return '사이클';
    case 'swimming':
      return '수영';
    default:
      return type;
  }
}

// 활동 타입 약어 (Runalyze 스타일: ER, LR, IT, TT 등)
export function getActivityTypeShort(type: string, name?: string | null): string {
  // 활동 이름에서 타입 추론 시도
  const nameLower = name?.toLowerCase() || '';

  // Long Run (LR) - 장거리 러닝
  if (nameLower.includes('long') || nameLower.includes('롱런') ||
      nameLower.includes('장거리') || nameLower.includes('lsd')) return 'LR';

  // Easy Run (ER) - 이지 러닝
  if (nameLower.includes('easy') || nameLower.includes('이지') ||
      nameLower.includes('조깅') || nameLower.includes('jog')) return 'ER';

  // Interval (IT) - 인터벌
  if (nameLower.includes('interval') || nameLower.includes('인터벌') ||
      nameLower.includes('반복') || nameLower.includes('repeat')) return 'IT';

  // Tempo/Threshold (TT) - 템포/역치
  if (nameLower.includes('tempo') || nameLower.includes('템포') ||
      nameLower.includes('threshold') || nameLower.includes('역치') ||
      nameLower.includes('cruise')) return 'TT';

  // Recovery (RC) - 회복
  if (nameLower.includes('recovery') || nameLower.includes('회복') ||
      nameLower.includes('리커버리')) return 'RC';

  // Race (RA) - 대회/레이스
  if (nameLower.includes('race') || nameLower.includes('대회') ||
      nameLower.includes('마라톤') || nameLower.includes('하프') ||
      nameLower.includes('10k') || nameLower.includes('5k')) return 'RA';

  // Trail (TR) - 트레일
  if (nameLower.includes('trail') || nameLower.includes('트레일') ||
      nameLower.includes('산') || nameLower.includes('hill')) return 'TR';

  // Treadmill (TM) - 트레드밀
  if (nameLower.includes('treadmill') || nameLower.includes('트레드밀') ||
      nameLower.includes('러닝머신') || nameLower.includes('실내')) return 'TM';

  // Fartlek (FK) - 파틀렉
  if (nameLower.includes('fartlek') || nameLower.includes('파틀렉')) return 'FK';

  // 기본 타입 매핑
  switch (type) {
    case 'running':
      return 'ER'; // Easy Run 기본값
    case 'cycling':
      return 'CY';
    case 'swimming':
      return 'SW';
    case 'walking':
      return 'WK';
    case 'hiking':
      return 'HK';
    default:
      return '--';
  }
}

// Runalyze 스타일 날짜 포맷 (예: "29.12 Mon")
export function formatDateRunalyze(dateStr: string | Date): string {
  const date = parseDate(dateStr);
  if (!date) return '--';
  const day = String(date.getDate()).padStart(2, '0');
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const weekdays = ['일', '월', '화', '수', '목', '금', '토'];
  const weekday = weekdays[date.getDay()];
  return `${day}.${month} ${weekday}`;
}
