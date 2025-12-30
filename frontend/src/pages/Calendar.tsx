import { useState, useMemo } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Activity,
  Dumbbell,
  Plus,
  CalendarDays,
  Loader2,
} from 'lucide-react';
import clsx from 'clsx';
import { useCalendar } from '../hooks/useDashboard';
import { useStrengthCalendar, getSessionTypeLabel, getSessionTypeColor } from '../hooks/useStrength';
import type { CalendarDay, RecentActivity, UpcomingWorkout, StrengthSessionSummary } from '../types/api';

const WEEKDAYS = ['월', '화', '수', '목', '금', '토', '일'];
const WEEKDAYS_SHORT = ['월', '화', '수', '목', '금', '토', '일'];
const MONTHS = [
  '1월', '2월', '3월', '4월', '5월', '6월',
  '7월', '8월', '9월', '10월', '11월', '12월',
];

function getWorkoutTypeColor(type: string): string {
  switch (type) {
    case 'easy':
      return 'bg-green-500/20 border-green-500/40 text-green-400';
    case 'tempo':
      return 'bg-amber/20 border-amber/40 text-amber';
    case 'interval':
      return 'bg-red-500/20 border-red-500/40 text-red-400';
    case 'long':
      return 'bg-cyan/20 border-cyan/40 text-cyan';
    case 'steady':
      return 'bg-blue-500/20 border-blue-500/40 text-blue-400';
    default:
      return 'bg-gray-500/20 border-gray-500/40 text-gray-400';
  }
}

function getWorkoutTypeName(type: string): string {
  switch (type) {
    case 'easy':
      return '이지';
    case 'tempo':
      return '템포';
    case 'interval':
      return '인터벌';
    case 'long':
      return '장거리';
    case 'steady':
      return '스테디';
    default:
      return type;
  }
}

function formatDuration(minutes: number): string {
  const hours = Math.floor(minutes / 60);
  const mins = minutes % 60;
  if (hours > 0) {
    return `${hours}시간 ${mins}분`;
  }
  return `${mins}분`;
}

export function Calendar() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  // 월의 시작일과 종료일 계산
  const startDate = useMemo(() => {
    const d = new Date(year, month, 1);
    return d.toISOString().split('T')[0];
  }, [year, month]);

  const endDate = useMemo(() => {
    const d = new Date(year, month + 1, 0);
    return d.toISOString().split('T')[0];
  }, [year, month]);

  // API 호출
  const { data: calendarData, isLoading } = useCalendar({
    start_date: startDate,
    end_date: endDate,
  });

  // 보강운동 데이터 호출
  const { data: strengthData, isLoading: strengthLoading } = useStrengthCalendar(year, month + 1);

  // 날짜 데이터를 맵으로 변환
  const dateDataMap = useMemo(() => {
    const map = new Map<string, CalendarDay>();
    calendarData?.days.forEach(day => {
      map.set(day.date, day);
    });
    return map;
  }, [calendarData]);

  // 보강운동 데이터를 날짜별 맵으로 변환
  const strengthDataMap = useMemo(() => {
    const map = new Map<string, StrengthSessionSummary[]>();
    strengthData?.forEach(session => {
      const existing = map.get(session.session_date) || [];
      existing.push(session);
      map.set(session.session_date, existing);
    });
    return map;
  }, [strengthData]);

  // 첫째 날과 마지막 날 정보
  const firstDayOfMonth = new Date(year, month, 1);
  const lastDayOfMonth = new Date(year, month + 1, 0);
  const daysInMonth = lastDayOfMonth.getDate();

  // 월요일 시작 기준 조정
  let startDay = firstDayOfMonth.getDay() - 1;
  if (startDay < 0) startDay = 6;

  // 캘린더 날짜 배열 생성
  const calendarDays: (number | null)[] = [];
  for (let i = 0; i < startDay; i++) {
    calendarDays.push(null);
  }
  for (let day = 1; day <= daysInMonth; day++) {
    calendarDays.push(day);
  }

  // 네비게이션 함수
  const goToPreviousMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
    setSelectedDate(null);
  };

  const goToNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
    setSelectedDate(null);
  };

  const goToToday = () => {
    setCurrentDate(new Date());
    setSelectedDate(null);
  };

  // 날짜별 데이터 가져오기
  const getDateData = (day: number): CalendarDay | null => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return dateDataMap.get(dateStr) || null;
  };

  // 날짜별 보강운동 데이터 가져오기
  const getStrengthData = (day: number): StrengthSessionSummary[] => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return strengthDataMap.get(dateStr) || [];
  };

  // 오늘 확인
  const isToday = (day: number) => {
    const today = new Date();
    return (
      day === today.getDate() &&
      month === today.getMonth() &&
      year === today.getFullYear()
    );
  };

  // 선택된 날짜 데이터
  const selectedDateData = selectedDate ? dateDataMap.get(selectedDate) : null;
  const selectedStrengthData = selectedDate ? strengthDataMap.get(selectedDate) || [] : [];

  // 예정된 운동 필터링
  const upcomingWorkouts = useMemo(() => {
    const today = new Date().toISOString().split('T')[0];
    const workouts: { date: string; workout: UpcomingWorkout }[] = [];

    calendarData?.days.forEach(day => {
      if (day.date >= today && day.scheduled_workouts.length > 0) {
        day.scheduled_workouts.forEach(w => {
          workouts.push({ date: day.date, workout: w });
        });
      }
    });

    return workouts.sort((a, b) => a.date.localeCompare(b.date)).slice(0, 4);
  }, [calendarData]);

  return (
    <div className="space-y-4 md:space-y-6">
      {/* 페이지 헤더 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl md:text-2xl font-display font-bold flex items-center gap-2">
            <CalendarDays className="w-6 h-6 text-cyan" />
            캘린더
          </h1>
          <p className="text-muted text-sm mt-1">훈련 일정을 관리하세요</p>
        </div>
        <button className="btn btn-primary flex items-center justify-center gap-2 w-full sm:w-auto">
          <Plus className="w-4 h-4" />
          운동 추가
        </button>
      </div>

      {/* 메인 그리드 - 모바일에서는 단일 컬럼 */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 md:gap-6">
        {/* 캘린더 그리드 */}
        <div className="lg:col-span-2 card p-4 md:p-6">
          {/* 캘린더 헤더 */}
          <div className="flex items-center justify-between mb-4 md:mb-6">
            <h2 className="text-lg md:text-xl font-display font-bold">
              {year}년 {MONTHS[month]}
            </h2>
            <div className="flex items-center gap-1 md:gap-2">
              <button
                onClick={goToToday}
                className="btn btn-secondary text-xs md:text-sm px-2 md:px-3 py-1"
              >
                오늘
              </button>
              <button
                onClick={goToPreviousMonth}
                className="btn btn-secondary p-1.5 md:p-2"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={goToNextMonth}
                className="btn btn-secondary p-1.5 md:p-2"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* 로딩 상태 */}
          {isLoading || strengthLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="w-8 h-8 text-cyan animate-spin" />
            </div>
          ) : (
            <>
              {/* 요일 헤더 */}
              <div className="grid grid-cols-7 gap-0.5 md:gap-1 mb-1 md:mb-2">
                {(window.innerWidth < 768 ? WEEKDAYS_SHORT : WEEKDAYS).map((day, index) => (
                  <div
                    key={day}
                    className={clsx(
                      'text-center text-xs font-medium uppercase tracking-wider py-1.5 md:py-2',
                      index === 5 ? 'text-blue-400' : '',
                      index === 6 ? 'text-red-400' : '',
                      index < 5 ? 'text-muted' : ''
                    )}
                  >
                    {day}
                  </div>
                ))}
              </div>

              {/* 캘린더 날짜 */}
              <div className="grid grid-cols-7 gap-0.5 md:gap-1">
                {calendarDays.map((day, index) => {
                  if (day === null) {
                    return <div key={`empty-${index}`} className="h-14 md:h-24" />;
                  }

                  const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                  const data = getDateData(day);
                  const strengthSessions = getStrengthData(day);
                  const hasActivity = data && data.activities.length > 0;
                  const hasWorkout = data && data.scheduled_workouts.length > 0;
                  const hasStrength = strengthSessions.length > 0;
                  const isSelected = selectedDate === dateStr;
                  const dayOfWeek = (startDay + day - 1) % 7;
                  const isSaturday = dayOfWeek === 5;
                  const isSunday = dayOfWeek === 6;

                  return (
                    <button
                      key={day}
                      onClick={() => setSelectedDate(dateStr)}
                      className={clsx(
                        'h-14 md:h-24 p-1 md:p-2 rounded-lg border transition-all text-left',
                        'hover:border-cyan/30 hover:bg-[var(--color-bg-tertiary)]',
                        isSelected && 'border-cyan bg-cyan/5',
                        !isSelected && 'border-transparent',
                        isToday(day) && 'ring-2 ring-cyan/50'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <span
                          className={clsx(
                            'text-xs md:text-sm font-medium',
                            isToday(day) && 'text-cyan',
                            isSaturday && !isToday(day) && 'text-blue-400',
                            isSunday && !isToday(day) && 'text-red-400'
                          )}
                        >
                          {day}
                        </span>
                        {/* 모바일: 점 표시 */}
                        <div className="flex gap-0.5 md:hidden">
                          {hasActivity && (
                            <div className="w-1.5 h-1.5 rounded-full bg-cyan" />
                          )}
                          {hasStrength && (
                            <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                          )}
                          {hasWorkout && (
                            <div className="w-1.5 h-1.5 rounded-full bg-amber" />
                          )}
                        </div>
                        {/* 데스크톱: 점 표시 */}
                        <div className="hidden md:flex gap-1">
                          {hasActivity && (
                            <div className="w-2 h-2 rounded-full bg-cyan" />
                          )}
                          {hasStrength && (
                            <div className="w-2 h-2 rounded-full bg-purple-500" />
                          )}
                          {hasWorkout && (
                            <div className="w-2 h-2 rounded-full bg-amber" />
                          )}
                        </div>
                      </div>

                      {/* 데스크톱: 활동/운동 미리보기 */}
                      <div className="hidden md:block mt-1 space-y-1">
                        {data?.activities.slice(0, 1).map((activity) => (
                          <div
                            key={activity.id}
                            className="text-xs truncate text-cyan/80 flex items-center gap-1"
                          >
                            <Activity className="w-3 h-3 flex-shrink-0" />
                            {activity.distance_km}km
                          </div>
                        ))}
                        {strengthSessions.slice(0, 1).map((session) => (
                          <div
                            key={session.id}
                            className="text-xs truncate text-purple-400/80 flex items-center gap-1"
                          >
                            <Dumbbell className="w-3 h-3 flex-shrink-0" />
                            {getSessionTypeLabel(session.session_type)}
                          </div>
                        ))}
                        {data?.scheduled_workouts.slice(0, 1).map((workout) => (
                          <div
                            key={workout.id}
                            className={clsx(
                              'text-xs truncate px-1 py-0.5 rounded border',
                              getWorkoutTypeColor(workout.workout_type)
                            )}
                          >
                            {workout.workout_name}
                          </div>
                        ))}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* 범례 */}
              <div className="flex items-center gap-4 md:gap-6 mt-4 md:mt-6 pt-3 md:pt-4 border-t border-[var(--color-border)] flex-wrap">
                <div className="flex items-center gap-2 text-xs md:text-sm text-muted">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-cyan" />
                  <span>러닝</span>
                </div>
                <div className="flex items-center gap-2 text-xs md:text-sm text-muted">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-purple-500" />
                  <span>보강운동</span>
                </div>
                <div className="flex items-center gap-2 text-xs md:text-sm text-muted">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-amber" />
                  <span>예정된 운동</span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* 날짜 상세 패널 */}
        <div className="card p-4 md:p-6">
          <h3 className="text-base md:text-lg font-display font-bold mb-4">
            {selectedDate
              ? new Date(selectedDate + 'T00:00:00').toLocaleDateString('ko-KR', {
                  month: 'long',
                  day: 'numeric',
                  weekday: 'long',
                })
              : '날짜를 선택하세요'}
          </h3>

          {selectedDateData ? (
            <div className="space-y-4">
              {/* 활동 */}
              {selectedDateData.activities.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted uppercase tracking-wider mb-2">
                    완료한 활동
                  </h4>
                  {selectedDateData.activities.map((activity: RecentActivity) => (
                    <div
                      key={activity.id}
                      className="p-3 rounded-lg bg-[var(--color-bg-tertiary)] border border-cyan/20"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <Activity className="w-4 h-4 text-cyan" />
                        <span className="font-medium text-sm">{activity.name || '러닝'}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs md:text-sm">
                        <div>
                          <span className="text-muted">거리:</span>{' '}
                          <span className="font-mono">{activity.distance_km} km</span>
                        </div>
                        <div>
                          <span className="text-muted">시간:</span>{' '}
                          <span className="font-mono">
                            {activity.duration_seconds ? formatDuration(activity.duration_seconds) : '-'}
                          </span>
                        </div>
                        {activity.avg_hr_percent && (
                          <div className="col-span-2">
                            <span className="text-muted">평균 심박:</span>{' '}
                            <span className="font-mono text-red-400">{activity.avg_hr_percent} %</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 보강운동 */}
              {selectedStrengthData.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted uppercase tracking-wider mb-2">
                    보강운동
                  </h4>
                  {selectedStrengthData.map((session: StrengthSessionSummary) => (
                    <div
                      key={session.id}
                      className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/30"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <Dumbbell className="w-4 h-4 text-purple-400" />
                        <span className="font-medium text-sm text-purple-400">
                          {getSessionTypeLabel(session.session_type)}
                        </span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs md:text-sm">
                        <div>
                          <span className="text-muted">종목:</span>{' '}
                          <span className="font-mono">{session.exercise_count}</span>
                        </div>
                        <div>
                          <span className="text-muted">세트:</span>{' '}
                          <span className="font-mono">{session.total_sets}</span>
                        </div>
                        {session.duration_minutes && (
                          <div className="col-span-2">
                            <span className="text-muted">시간:</span>{' '}
                            <span className="font-mono">{session.duration_minutes}분</span>
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 예정된 운동 */}
              {selectedDateData.scheduled_workouts.length > 0 && (
                <div>
                  <h4 className="text-xs font-medium text-muted uppercase tracking-wider mb-2">
                    예정된 운동
                  </h4>
                  {selectedDateData.scheduled_workouts.map((workout: UpcomingWorkout) => (
                    <div
                      key={workout.id}
                      className={clsx(
                        'p-3 rounded-lg border',
                        getWorkoutTypeColor(workout.workout_type)
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Dumbbell className="w-4 h-4" />
                        <span className="font-medium text-sm">{workout.workout_name}</span>
                      </div>
                      <div className="mt-1 text-xs opacity-80">
                        유형: {getWorkoutTypeName(workout.workout_type)}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* 데이터 없음 */}
              {selectedDateData.activities.length === 0 &&
                selectedDateData.scheduled_workouts.length === 0 &&
                selectedStrengthData.length === 0 && (
                  <div className="text-center py-6 md:py-8 text-muted">
                    <p className="text-sm">활동이나 운동이 없습니다</p>
                    <button className="btn btn-secondary mt-4 text-sm">
                      운동 추가하기
                    </button>
                  </div>
                )}
            </div>
          ) : (
            <div className="text-center py-8 md:py-12 text-muted">
              <CalendarDays className="w-12 h-12 mx-auto mb-3 opacity-30" />
              <p className="text-sm">날짜를 클릭하면 상세 정보를 볼 수 있습니다</p>
            </div>
          )}
        </div>
      </div>

      {/* 예정된 운동 */}
      {upcomingWorkouts.length > 0 && (
        <div className="card p-4 md:p-6">
          <h3 className="text-base md:text-lg font-display font-bold mb-4">다가오는 운동</h3>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 md:gap-4">
            {upcomingWorkouts.map(({ date, workout }) => (
              <div
                key={`${date}-${workout.id}`}
                className="p-3 md:p-4 rounded-lg bg-[var(--color-bg-tertiary)] border border-[var(--color-border)]"
              >
                <p className="text-xs text-muted mb-2">
                  {new Date(date + 'T00:00:00').toLocaleDateString('ko-KR', {
                    month: 'short',
                    day: 'numeric',
                    weekday: 'short',
                  })}
                </p>
                <p className="font-medium text-sm mb-1">{workout.workout_name}</p>
                <span
                  className={clsx(
                    'text-xs px-2 py-0.5 rounded inline-block',
                    getWorkoutTypeColor(workout.workout_type)
                  )}
                >
                  {getWorkoutTypeName(workout.workout_type)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
