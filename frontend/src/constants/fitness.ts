/**
 * 피트니스 관련 상수
 * TSB, A:C 비율, 페이스 존 임계값 등
 */

// -------------------------------------------------------------------------
// TSB (Training Stress Balance) 상태 구간
// -------------------------------------------------------------------------

export const TSB_THRESHOLDS = {
  /** TSB > 25: 상쾌함 - 충분한 휴식 상태 */
  FRESH: 25,
  /** TSB > 5: 준비됨 - 훈련/레이스 준비 완료 */
  READY: 5,
  /** TSB > -10: 보통 - 일반적인 훈련 상태 */
  NORMAL: -10,
  /** TSB > -25: 피로 - 피로 누적 중 */
  TIRED: -25,
  /** TSB <= -25: 과부하 - 휴식 필요 */
  // OVERLOADED: 그 이하
} as const;

/** TSB 과훈련 경고 임계값 */
export const TSB_OVERTRAINING_THRESHOLD = -30;

// -------------------------------------------------------------------------
// A:C Ratio (Acute:Chronic Workload Ratio) 임계값
// 연구 기반: Gabbett TJ (2016) - "sweet spot" 0.8~1.3
// -------------------------------------------------------------------------

export const AC_RATIO_THRESHOLDS = {
  /** A:C < 0.8: 훈련량 부족, 컨디션 저하 위험 */
  UNDERTRAINED: 0.8,
  /** A:C 0.8~1.3: 최적 훈련 구간 (sweet spot) */
  OPTIMAL_MIN: 0.8,
  OPTIMAL_MAX: 1.3,
  /** A:C > 1.5: 급격한 훈련량 증가, 부상 위험 증가 */
  INJURY_RISK: 1.5,
} as const;

// -------------------------------------------------------------------------
// 페이스 존 (Pace Zones) - 초/km 기준
// 사용자 VDOT 기반 동적 계산이 이상적이나, 기본값으로 사용
// -------------------------------------------------------------------------

export const PACE_ZONE_THRESHOLDS = {
  /** < 270초 (4:30/km): 스피드 */
  SPEED: 270,
  /** < 300초 (5:00/km): 템포 */
  TEMPO: 300,
  /** < 360초 (6:00/km): 안정 */
  STEADY: 360,
  /** >= 360초: 이지 */
  // EASY: 그 이상
} as const;

// -------------------------------------------------------------------------
// TSB 상태 레이블 및 스타일
// -------------------------------------------------------------------------

export type TSBStatusKey = 'fresh' | 'ready' | 'normal' | 'tired' | 'overloaded' | 'unknown';

export interface TSBStatusConfig {
  label: string;
  labelEn: string;
  color: string;
  bg: string;
}

export const TSB_STATUS_CONFIG: Record<TSBStatusKey, TSBStatusConfig> = {
  fresh: {
    label: '상쾌함',
    labelEn: 'Fresh',
    color: 'text-positive',
    bg: 'bg-positive-soft',
  },
  ready: {
    label: '준비됨',
    labelEn: 'Ready',
    color: 'text-accent',
    bg: 'bg-accent-soft',
  },
  normal: {
    label: '보통',
    labelEn: 'Normal',
    color: 'text-ink',
    bg: 'bg-secondary',
  },
  tired: {
    label: '피로',
    labelEn: 'Tired',
    color: 'text-warning',
    bg: 'bg-warning-soft',
  },
  overloaded: {
    label: '과부하',
    labelEn: 'Overloaded',
    color: 'text-danger',
    bg: 'bg-danger-soft',
  },
  unknown: {
    label: '데이터 없음',
    labelEn: 'No Data',
    color: 'text-muted',
    bg: 'bg-secondary',
  },
};

// -------------------------------------------------------------------------
// Helper Functions
// -------------------------------------------------------------------------

/**
 * TSB 값으로 상태 키 반환
 */
export function getTSBStatusKey(tsb: number | null): TSBStatusKey {
  if (tsb === null) return 'unknown';
  if (tsb > TSB_THRESHOLDS.FRESH) return 'fresh';
  if (tsb > TSB_THRESHOLDS.READY) return 'ready';
  if (tsb > TSB_THRESHOLDS.NORMAL) return 'normal';
  if (tsb > TSB_THRESHOLDS.TIRED) return 'tired';
  return 'overloaded';
}

/**
 * TSB 값으로 상태 설정 반환
 */
export function getTSBStatus(tsb: number | null): TSBStatusConfig {
  return TSB_STATUS_CONFIG[getTSBStatusKey(tsb)];
}

/**
 * 부상 위험 요소 분석
 */
export function analyzeInjuryRisks(
  tsb: number | null,
  workloadRatio: number | null
): string[] {
  const risks: string[] = [];

  // TSB 과훈련 체크
  if (tsb !== null && tsb < TSB_OVERTRAINING_THRESHOLD) {
    risks.push('과훈련 위험: 휴식이 필요합니다');
  }

  // A:C 비율 체크
  if (workloadRatio !== null) {
    if (workloadRatio > AC_RATIO_THRESHOLDS.INJURY_RISK) {
      risks.push(`A:C 비율 ${workloadRatio.toFixed(2)}: 급격한 훈련량 증가`);
    } else if (workloadRatio < AC_RATIO_THRESHOLDS.UNDERTRAINED) {
      risks.push('훈련량 부족: 컨디션 저하 위험');
    }
  }

  return risks;
}
