// 지표 설명 사전
export const metricDescriptions: Record<string, string> = {
  // 훈련 지표
  calories: '활동 중 소모한 총 칼로리. 심박수, 체중, 운동 강도를 기반으로 계산됩니다.',
  elevation_gain: '러닝 중 오르막으로 얻은 총 고도. GPS와 기압계 데이터로 측정합니다.',
  elevation_loss: '러닝 중 내리막으로 잃은 총 고도.',
  training_effect: 'Garmin Training Effect. 1.0-5.0 범위로 유산소 능력 향상 정도를 나타냅니다. 3.0-4.0이 효과적인 훈련입니다.',
  trimp: 'Training Impulse. 운동 시간과 심박수 강도를 결합한 훈련 부하 지표입니다.',
  tss: 'Training Stress Score. 파워 기반 훈련 스트레스 점수. 100은 FTP로 1시간 운동한 것과 같습니다.',
  intensity_factor: 'Intensity Factor (IF). NP/FTP 비율로 운동 강도를 나타냅니다. 1.0은 FTP 수준입니다.',

  // 파워 & 효율
  avg_power: '활동 전체의 평균 출력 (와트). Stryd 파워미터로 측정합니다.',
  normalized_power: 'Normalized Power (NP). 가변성을 고려한 평균 파워. 인터벌 훈련 시 평균 파워보다 더 정확한 강도 지표입니다.',
  power_to_hr: 'Power-to-Heart Rate 비율 (W/bpm). 효율성 지표로, 높을수록 같은 심박에서 더 많은 파워를 냅니다.',
  vo2max: '추정 최대 산소 섭취량 (ml/kg/min). 유산소 체력의 핵심 지표입니다.',
  running_effectiveness: 'Running Effectiveness (m/kJ). 1kJ당 이동 거리. 높을수록 효율적인 러닝입니다.',

  // 러닝 폼
  cadence: '분당 걸음 수 (spm). 일반적으로 170-180 spm이 효율적입니다.',
  ground_time: 'Ground Contact Time (GCT). 발이 지면에 닿아있는 시간 (ms). 짧을수록 효율적입니다.',
  vertical_oscillation: 'Vertical Oscillation (VO). 상하 움직임 (cm). 낮을수록 에너지 손실이 적습니다.',
  leg_spring_stiffness: 'Leg Spring Stiffness (LSS). 다리 스프링 강성 (kN/m). 높을수록 탄성이 좋습니다.',
  form_power: 'Form Power. 자세 유지에 사용되는 파워 (W). 낮을수록 효율적인 폼입니다.',
};
