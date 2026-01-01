import { useState, useMemo, useRef, useCallback, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ChevronLeft,
  ChevronRight,
  Activity,
  Dumbbell,
  Plus,
  CalendarDays,
  Loader2,
  StickyNote,
  X,
  Save,
  Trash2,
  GripVertical,
  Trophy,
  MapPin,
  Target,
  Flag,
  Star,
  Edit3,
  ChevronRightIcon,
} from 'lucide-react';
import clsx from 'clsx';
import { useCalendar } from '../hooks/useDashboard';
import { useStrengthCalendar, getSessionTypeLabel } from '../hooks/useStrength';
import { useCalendarNotes, useCreateOrUpdateNote, useDeleteNote } from '../hooks/useCalendarNotes';
import { useRaces, useUpcomingRace, useCreateRace, useUpdateRace, useDeleteRace, useGarminPredictions } from '../hooks/useRaces';
import type { CalendarDay, RecentActivity, UpcomingWorkout, StrengthSessionSummary, CalendarNote } from '../types/api';
import type { Race, RaceCreate, RaceUpdate, GarminRacePrediction } from '../api/races';

// 대회 거리 옵션
const RACE_DISTANCES = [
  { value: 5, label: '5K' },
  { value: 10, label: '10K' },
  { value: 21.0975, label: '하프마라톤' },
  { value: 42.195, label: '풀마라톤' },
  { value: 100, label: '울트라 (100K)' },
  { value: 0, label: '기타' },
];

// 시간을 초로 변환
function timeToSeconds(hours: number, minutes: number, seconds: number): number {
  return hours * 3600 + minutes * 60 + seconds;
}

// 초를 시간 문자열로 변환
function secondsToTimeString(totalSeconds: number | null): string {
  if (!totalSeconds) return '-';
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  if (hours > 0) {
    return `${hours}:${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}`;
  }
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

// 초를 시/분/초 객체로 변환
function secondsToTime(totalSeconds: number | null): { hours: number; minutes: number; seconds: number } {
  if (!totalSeconds) return { hours: 0, minutes: 0, seconds: 0 };
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return { hours, minutes, seconds };
}

// 메모 타입 정보
type NoteTypeValue = 'memo' | 'injury' | 'event' | 'rest' | 'goal';
const NOTE_TYPES: { value: NoteTypeValue; label: string; icon: string }[] = [
  { value: 'memo', label: '메모', icon: '📝' },
  { value: 'injury', label: '부상', icon: '🩹' },
  { value: 'event', label: '이벤트', icon: '🏃' },
  { value: 'rest', label: '휴식', icon: '😴' },
  { value: 'goal', label: '목표', icon: '🎯' },
];

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

function formatDurationSeconds(seconds: number | null | undefined): string {
  if (!seconds) return '-';
  const totalMinutes = Math.floor(seconds / 60);
  const hours = Math.floor(totalMinutes / 60);
  const mins = totalMinutes % 60;
  if (hours > 0) {
    return `${hours}시간 ${mins}분`;
  }
  return `${mins}분`;
}

// 로컬 스토리지에서 패널 너비 불러오기
const getSavedPanelWidth = () => {
  if (typeof window === 'undefined') return 320;
  const saved = localStorage.getItem('calendar-panel-width');
  return saved ? parseInt(saved, 10) : 320;
};

export function Calendar() {
  const navigate = useNavigate();
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  // 메모 편집 상태
  const [isEditingNote, setIsEditingNote] = useState(false);
  const [noteContent, setNoteContent] = useState('');
  const [noteType, setNoteType] = useState<NoteTypeValue>('memo');

  // 대회 모달 상태
  const [isRaceModalOpen, setIsRaceModalOpen] = useState(false);
  const [editingRace, setEditingRace] = useState<Race | null>(null);
  const [raceForm, setRaceForm] = useState({
    name: '',
    race_date: '',
    distance_km: 0,
    distance_label: '',
    location: '',
    goal_hours: 0,
    goal_minutes: 0,
    goal_seconds: 0,
    goal_description: '',
    is_primary: false,
  });
  const [showGarminPredictions, setShowGarminPredictions] = useState(false);

  // 리사이즈 상태
  const [panelWidth, setPanelWidth] = useState(getSavedPanelWidth);
  const [isResizing, setIsResizing] = useState(false);
  const [isDesktop, setIsDesktop] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  // 패널 너비 저장
  useEffect(() => {
    localStorage.setItem('calendar-panel-width', panelWidth.toString());
  }, [panelWidth]);

  // 반응형 체크
  useEffect(() => {
    const checkDesktop = () => setIsDesktop(window.innerWidth >= 1024);
    checkDesktop();
    window.addEventListener('resize', checkDesktop);
    return () => window.removeEventListener('resize', checkDesktop);
  }, []);

  // 리사이즈 핸들러
  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (!isResizing || !containerRef.current) return;

    const containerRect = containerRef.current.getBoundingClientRect();
    const newWidth = containerRect.right - e.clientX;

    // 최소 200px, 최대 600px
    const clampedWidth = Math.min(Math.max(newWidth, 200), 600);
    setPanelWidth(clampedWidth);
  }, [isResizing]);

  const handleMouseUp = useCallback(() => {
    setIsResizing(false);
  }, []);

  // 리사이즈 이벤트 리스너
  useEffect(() => {
    if (isResizing) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = 'col-resize';
      document.body.style.userSelect = 'none';
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';
    };
  }, [isResizing, handleMouseMove, handleMouseUp]);

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

  // 메모 데이터 호출
  const { data: notesData } = useCalendarNotes({
    start_date: startDate,
    end_date: endDate,
  });
  const createOrUpdateNote = useCreateOrUpdateNote();
  const deleteNote = useDeleteNote();

  // 대회 데이터 호출
  const { data: racesData } = useRaces(true); // 완료된 대회도 포함
  const { data: upcomingRace } = useUpcomingRace();
  const createRace = useCreateRace();
  const updateRace = useUpdateRace();
  const deleteRace = useDeleteRace();
  const { data: garminPredictions } = useGarminPredictions();

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

  // 메모 데이터를 날짜별 맵으로 변환
  const notesDataMap = useMemo(() => {
    const map = new Map<string, CalendarNote>();
    notesData?.notes.forEach(note => {
      map.set(note.date, note);
    });
    return map;
  }, [notesData]);

  // 대회 데이터를 날짜별 맵으로 변환
  const racesDataMap = useMemo(() => {
    const map = new Map<string, Race>();
    racesData?.races.forEach(race => {
      map.set(race.race_date, race);
    });
    return map;
  }, [racesData]);

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

  // 날짜별 메모 데이터 가져오기
  const getNoteData = (day: number): CalendarNote | null => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return notesDataMap.get(dateStr) || null;
  };

  // 날짜별 대회 데이터 가져오기
  const getRaceData = (day: number): Race | null => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return racesDataMap.get(dateStr) || null;
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
  const selectedNoteData = selectedDate ? notesDataMap.get(selectedDate) : null;
  const selectedRaceData = selectedDate ? racesDataMap.get(selectedDate) : null;

  // 메모 편집 시작
  const startEditNote = () => {
    if (selectedNoteData) {
      setNoteContent(selectedNoteData.content);
      setNoteType(selectedNoteData.note_type);
    } else {
      setNoteContent('');
      setNoteType('memo');
    }
    setIsEditingNote(true);
  };

  // 메모 저장
  const handleSaveNote = async () => {
    if (!selectedDate || !noteContent.trim()) return;

    const noteTypeInfo = NOTE_TYPES.find(t => t.value === noteType);
    await createOrUpdateNote.mutateAsync({
      date: selectedDate,
      note_type: noteType,
      content: noteContent.trim(),
      icon: noteTypeInfo?.icon || null,
    });
    setIsEditingNote(false);
  };

  // 메모 삭제
  const handleDeleteNote = async () => {
    if (!selectedDate) return;
    await deleteNote.mutateAsync(selectedDate);
    setIsEditingNote(false);
    setNoteContent('');
    setNoteType('memo');
  };

  // 메모 편집 취소
  const cancelEditNote = () => {
    setIsEditingNote(false);
    setNoteContent('');
    setNoteType('memo');
  };

  // 대회 등록 모달 열기
  const openRaceModal = (race?: Race) => {
    if (race) {
      // 수정 모드
      setEditingRace(race);
      const goalTime = secondsToTime(race.goal_time_seconds);
      setRaceForm({
        name: race.name,
        race_date: race.race_date,
        distance_km: race.distance_km || 0,
        distance_label: race.distance_label || '',
        location: race.location || '',
        goal_hours: goalTime.hours,
        goal_minutes: goalTime.minutes,
        goal_seconds: goalTime.seconds,
        goal_description: race.goal_description || '',
        is_primary: race.is_primary,
      });
    } else {
      // 새로 등록
      setEditingRace(null);
      setRaceForm({
        name: '',
        race_date: selectedDate || new Date().toISOString().split('T')[0],
        distance_km: 42.195,
        distance_label: '풀마라톤',
        location: '',
        goal_hours: 0,
        goal_minutes: 0,
        goal_seconds: 0,
        goal_description: '',
        is_primary: false,
      });
    }
    setIsRaceModalOpen(true);
  };

  // 대회 모달 닫기
  const closeRaceModal = () => {
    setIsRaceModalOpen(false);
    setEditingRace(null);
  };

  // 대회 저장
  const handleSaveRace = async () => {
    const goalSeconds = timeToSeconds(raceForm.goal_hours, raceForm.goal_minutes, raceForm.goal_seconds);

    const raceData: RaceCreate = {
      name: raceForm.name,
      race_date: raceForm.race_date,
      distance_km: raceForm.distance_km || null,
      distance_label: raceForm.distance_label || null,
      location: raceForm.location || null,
      goal_time_seconds: goalSeconds > 0 ? goalSeconds : null,
      goal_description: raceForm.goal_description || null,
      is_primary: raceForm.is_primary,
    };

    if (editingRace) {
      await updateRace.mutateAsync({ raceId: editingRace.id, race: raceData as RaceUpdate });
    } else {
      await createRace.mutateAsync(raceData);
    }
    closeRaceModal();
  };

  // 대회 삭제
  const handleDeleteRace = async () => {
    if (!editingRace) return;
    if (confirm('이 대회를 삭제하시겠습니까?')) {
      await deleteRace.mutateAsync(editingRace.id);
      closeRaceModal();
    }
  };

  // 거리 선택 핸들러
  const handleDistanceChange = (value: number, label: string) => {
    setRaceForm(prev => ({
      ...prev,
      distance_km: value,
      distance_label: label,
    }));
  };

  // Garmin 예측 적용 핸들러
  const applyGarminPrediction = (prediction: GarminRacePrediction) => {
    const time = secondsToTime(prediction.predicted_time_seconds);
    const distanceInfo = RACE_DISTANCES.find(d => Math.abs(d.value - prediction.distance_km) < 0.1);

    setRaceForm(prev => ({
      ...prev,
      distance_km: prediction.distance_km,
      distance_label: distanceInfo?.label || prediction.distance,
      goal_hours: time.hours,
      goal_minutes: time.minutes,
      goal_seconds: time.seconds,
      goal_description: `Garmin VO2Max 기반 예측 (${garminPredictions?.vo2_max ? `VO2Max: ${garminPredictions.vo2_max}` : ''})`,
    }));
    setShowGarminPredictions(false);
  };

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

  // 월간 마일리지 계산
  const monthlyStats = useMemo(() => {
    if (!calendarData?.days) return { totalKm: 0, totalSeconds: 0, activityCount: 0 };

    let totalKm = 0;
    let totalSeconds = 0;
    let activityCount = 0;

    calendarData.days.forEach(day => {
      day.activities.forEach(activity => {
        totalKm += activity.distance_km || 0;
        totalSeconds += activity.duration_seconds || 0;
        activityCount += 1;
      });
    });

    return { totalKm, totalSeconds, activityCount };
  }, [calendarData]);

  return (
    <div className="space-y-4 md:space-y-6">
      {/* D-Day 배너 */}
      {upcomingRace && (
        <div className="card-accent p-4 md:p-5 bg-gradient-to-r from-amber/10 via-amber/5 to-transparent border-amber/30">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="flex-shrink-0 w-16 h-16 md:w-20 md:h-20 rounded-lg bg-amber/20 flex flex-col items-center justify-center border border-amber/30">
                <span className="text-xs text-amber/80 font-medium">D-DAY</span>
                <span className="text-2xl md:text-3xl font-mono font-bold text-amber">
                  {upcomingRace.days_until === 0 ? 'TODAY' : upcomingRace.days_until > 0 ? `-${upcomingRace.days_until}` : `+${Math.abs(upcomingRace.days_until)}`}
                </span>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <Trophy className="w-4 h-4 text-amber" />
                  <h2 className="text-lg md:text-xl font-display font-bold truncate">{upcomingRace.name}</h2>
                  {upcomingRace.is_primary && (
                    <Star className="w-4 h-4 text-amber fill-amber" />
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted">
                  <span className="flex items-center gap-1">
                    <CalendarDays className="w-3.5 h-3.5" />
                    {new Date(upcomingRace.race_date + 'T00:00:00').toLocaleDateString('ko-KR', {
                      year: 'numeric',
                      month: 'long',
                      day: 'numeric',
                      weekday: 'short',
                    })}
                  </span>
                  {upcomingRace.location && (
                    <span className="flex items-center gap-1">
                      <MapPin className="w-3.5 h-3.5" />
                      {upcomingRace.location}
                    </span>
                  )}
                  {upcomingRace.distance_label && (
                    <span className="flex items-center gap-1">
                      <Flag className="w-3.5 h-3.5" />
                      {upcomingRace.distance_label}
                    </span>
                  )}
                </div>
                {upcomingRace.goal_time_seconds && (
                  <div className="mt-2 flex items-center gap-2">
                    <Target className="w-4 h-4 text-cyan" />
                    <span className="text-sm">
                      목표: <span className="font-mono text-cyan">{secondsToTimeString(upcomingRace.goal_time_seconds)}</span>
                    </span>
                  </div>
                )}
              </div>
            </div>
            <button
              onClick={() => openRaceModal(upcomingRace)}
              className="btn btn-secondary text-sm flex-shrink-0"
            >
              <Edit3 className="w-4 h-4" />
              수정
            </button>
          </div>
        </div>
      )}

      {/* 페이지 헤더 */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-xl md:text-2xl font-display font-bold flex items-center gap-2">
            <CalendarDays className="w-6 h-6 text-cyan" />
            캘린더
          </h1>
          <p className="text-muted text-sm mt-1">훈련 일정을 관리하세요</p>
        </div>
        <div className="flex gap-2 w-full sm:w-auto">
          <button
            onClick={() => openRaceModal()}
            className="btn btn-secondary flex items-center justify-center gap-2 flex-1 sm:flex-initial"
          >
            <Trophy className="w-4 h-4" />
            대회 등록
          </button>
          <button className="btn btn-primary flex items-center justify-center gap-2 flex-1 sm:flex-initial">
            <Plus className="w-4 h-4" />
            운동 추가
          </button>
        </div>
      </div>

      {/* 메인 레이아웃 - 리사이즈 가능한 flex 레이아웃 */}
      <div ref={containerRef} className="flex flex-col lg:flex-row gap-4 md:gap-6">
        {/* 캘린더 그리드 */}
        <div className="flex-1 min-w-0 card p-4 md:p-6">
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

          {/* 월간 마일리지 요약 */}
          {!isLoading && monthlyStats.activityCount > 0 && (
            <div className="mb-4 p-3 rounded-lg bg-cyan/5 border border-cyan/20">
              <div className="flex items-center justify-between flex-wrap gap-2">
                <div className="flex items-center gap-4 md:gap-6">
                  <div>
                    <span className="text-muted text-xs">월간 거리</span>
                    <div className="font-mono text-lg md:text-xl font-bold text-cyan">
                      {monthlyStats.totalKm.toFixed(1)} <span className="text-sm font-normal">km</span>
                    </div>
                  </div>
                  <div className="hidden sm:block">
                    <span className="text-muted text-xs">총 시간</span>
                    <div className="font-mono text-sm md:text-base text-muted">
                      {formatDurationSeconds(monthlyStats.totalSeconds)}
                    </div>
                  </div>
                  <div>
                    <span className="text-muted text-xs">활동</span>
                    <div className="font-mono text-sm md:text-base text-muted">
                      {monthlyStats.activityCount}회
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

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
                    return <div key={`empty-${index}`} className="h-16 md:h-28 lg:h-32" />;
                  }

                  const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
                  const data = getDateData(day);
                  const strengthSessions = getStrengthData(day);
                  const noteData = getNoteData(day);
                  const raceData = getRaceData(day);
                  const hasActivity = data && data.activities.length > 0;
                  const hasWorkout = data && data.scheduled_workouts.length > 0;
                  const hasStrength = strengthSessions.length > 0;
                  const hasNote = !!noteData;
                  const hasRace = !!raceData;
                  const isSelected = selectedDate === dateStr;
                  const dayOfWeek = (startDay + day - 1) % 7;
                  const isSaturday = dayOfWeek === 5;
                  const isSunday = dayOfWeek === 6;

                  return (
                    <button
                      key={day}
                      onClick={() => setSelectedDate(dateStr)}
                      className={clsx(
                        'h-16 md:h-28 lg:h-32 p-1 md:p-2 rounded-lg border transition-all text-left flex flex-col',
                        'hover:border-cyan/30 hover:bg-[var(--color-bg-tertiary)]',
                        isSelected && 'border-cyan bg-cyan/5',
                        !isSelected && !hasRace && 'border-transparent',
                        !isSelected && hasRace && 'border-amber/30 bg-amber/5',
                        isToday(day) && 'ring-2 ring-cyan/50',
                        hasRace && 'ring-2 ring-amber/40'
                      )}
                    >
                      {/* 날짜 행 - 고정 높이 */}
                      <div className="flex items-center justify-between flex-shrink-0">
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
                          {hasRace && (
                            <div className="w-1.5 h-1.5 rounded-full bg-amber ring-1 ring-amber/50" />
                          )}
                          {hasActivity && (
                            <div className="w-1.5 h-1.5 rounded-full bg-cyan" />
                          )}
                          {hasStrength && (
                            <div className="w-1.5 h-1.5 rounded-full bg-purple-500" />
                          )}
                          {hasWorkout && (
                            <div className="w-1.5 h-1.5 rounded-full bg-green-500" />
                          )}
                          {hasNote && (
                            <div className="w-1.5 h-1.5 rounded-full bg-yellow-500" />
                          )}
                        </div>
                        {/* 데스크톱: 점 표시 */}
                        <div className="hidden md:flex gap-1">
                          {hasRace && (
                            <div className="w-2 h-2 rounded-full bg-amber ring-1 ring-amber/50" />
                          )}
                          {hasActivity && (
                            <div className="w-2 h-2 rounded-full bg-cyan" />
                          )}
                          {hasStrength && (
                            <div className="w-2 h-2 rounded-full bg-purple-500" />
                          )}
                          {hasWorkout && (
                            <div className="w-2 h-2 rounded-full bg-green-500" />
                          )}
                          {hasNote && (
                            <div className="w-2 h-2 rounded-full bg-yellow-500" />
                          )}
                        </div>
                      </div>

                      {/* 데스크톱: 활동/운동 미리보기 */}
                      <div className="hidden md:flex flex-col flex-1 mt-1 space-y-0.5 overflow-hidden">
                        {/* 대회 표시 - 가장 먼저 */}
                        {raceData && (
                          <div className="text-[11px] truncate text-amber font-medium flex items-center gap-1 px-1 py-0.5 rounded bg-amber/10 border border-amber/30">
                            <Trophy className="w-3 h-3 flex-shrink-0" />
                            <span className="truncate">{raceData.name}</span>
                          </div>
                        )}
                        {data?.activities && data.activities.length > 0 && (() => {
                          const totalKm = data.activities.reduce((sum, a) => sum + (a.distance_km || 0), 0);
                          const totalTime = data.activities.reduce((sum, a) => sum + (a.duration_seconds || 0), 0);
                          const timeStr = totalTime > 0 ? `${Math.floor(totalTime / 60)}분` : '';
                          if (data.activities.length === 1) {
                            const name = data.activities[0].name || '러닝';
                            return (
                              <>
                                <div className="text-xs truncate text-cyan font-medium">{totalKm.toFixed(1)}km</div>
                                <div className="text-[10px] truncate text-cyan/60" title={name}>{name}</div>
                                {timeStr && <div className="text-[10px] truncate text-muted">{timeStr}</div>}
                              </>
                            );
                          } else {
                            return (
                              <>
                                <div className="text-xs truncate text-cyan font-medium">{totalKm.toFixed(1)}km</div>
                                <div className="text-[10px] truncate text-cyan/60">{data.activities.length}회 · {timeStr}</div>
                              </>
                            );
                          }
                        })()}
                        {strengthSessions.slice(0, 1).map((session) => (
                          <div
                            key={session.id}
                            className="text-[11px] truncate text-purple-400/80 flex items-center gap-1"
                          >
                            <Dumbbell className="w-3 h-3 flex-shrink-0" />
                            {getSessionTypeLabel(session.session_type)}
                          </div>
                        ))}
                        {data?.scheduled_workouts.slice(0, 1).map((workout) => (
                          <div
                            key={workout.id}
                            className={clsx(
                              'text-[11px] truncate px-1 py-0.5 rounded border',
                              getWorkoutTypeColor(workout.workout_type)
                            )}
                          >
                            {workout.workout_name}
                          </div>
                        ))}
                        {noteData && (
                          <div className="text-[11px] truncate text-yellow-500/80 flex items-center gap-1">
                            <span>{noteData.icon || '📝'}</span>
                            <span className="truncate">{NOTE_TYPES.find(t => t.value === noteData.note_type)?.label || '메모'}</span>
                          </div>
                        )}
                      </div>
                    </button>
                  );
                })}
              </div>

              {/* 범례 */}
              <div className="flex items-center gap-4 md:gap-6 mt-4 md:mt-6 pt-3 md:pt-4 border-t border-[var(--color-border)] flex-wrap">
                <div className="flex items-center gap-2 text-xs md:text-sm text-muted">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-amber ring-1 ring-amber/50" />
                  <span>대회</span>
                </div>
                <div className="flex items-center gap-2 text-xs md:text-sm text-muted">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-cyan" />
                  <span>러닝</span>
                </div>
                <div className="flex items-center gap-2 text-xs md:text-sm text-muted">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-purple-500" />
                  <span>보강운동</span>
                </div>
                <div className="flex items-center gap-2 text-xs md:text-sm text-muted">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-green-500" />
                  <span>예정된 운동</span>
                </div>
                <div className="flex items-center gap-2 text-xs md:text-sm text-muted">
                  <div className="w-2.5 h-2.5 md:w-3 md:h-3 rounded-full bg-yellow-500" />
                  <span>메모</span>
                </div>
              </div>
            </>
          )}
        </div>

        {/* 리사이즈 핸들 - 데스크톱에서만 표시 */}
        <div
          onMouseDown={handleMouseDown}
          className={clsx(
            'hidden lg:flex items-center justify-center w-2 cursor-col-resize group',
            'hover:bg-cyan/20 transition-colors rounded',
            isResizing && 'bg-cyan/30'
          )}
        >
          <GripVertical className="w-4 h-4 text-muted group-hover:text-cyan transition-colors" />
        </div>

        {/* 날짜 상세 패널 */}
        <div
          className="card p-4 md:p-6 lg:flex-shrink-0 overflow-y-auto w-full lg:w-auto"
          style={isDesktop ? { width: panelWidth, minWidth: 200, maxWidth: 600 } : undefined}
        >
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
                  {/* 복수 활동 시 합계 요약 표시 */}
                  {selectedDateData.activities.length > 1 && (
                    <div className="p-3 mb-2 rounded-lg bg-cyan/10 border border-cyan/30">
                      <div className="flex items-center gap-2 mb-1">
                        <Activity className="w-4 h-4 text-cyan" />
                        <span className="font-medium text-sm text-cyan">일일 합계</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-xs md:text-sm">
                        <div>
                          <span className="text-muted">총 거리:</span>{' '}
                          <span className="font-mono text-cyan">
                            {selectedDateData.activities.reduce((sum, a) => sum + (a.distance_km || 0), 0).toFixed(1)} km
                          </span>
                        </div>
                        <div>
                          <span className="text-muted">총 시간:</span>{' '}
                          <span className="font-mono text-cyan">
                            {formatDurationSeconds(selectedDateData.activities.reduce((sum, a) => sum + (a.duration_seconds || 0), 0))}
                          </span>
                        </div>
                      </div>
                    </div>
                  )}
                  <div className="space-y-2">
                    {selectedDateData.activities.map((activity: RecentActivity) => (
                      <div
                        key={activity.id}
                        onClick={() => navigate(`/activities/${activity.id}`)}
                        className="p-3 rounded-lg bg-[var(--color-bg-tertiary)] border border-cyan/20 cursor-pointer hover:border-cyan/50 hover:bg-cyan/5 transition-all group"
                      >
                        <div className="flex items-center justify-between mb-2">
                          <div className="flex items-center gap-2">
                            <Activity className="w-4 h-4 text-cyan" />
                            <span className="font-medium text-sm">{activity.name || '러닝'}</span>
                          </div>
                          <ChevronRightIcon className="w-4 h-4 text-muted group-hover:text-cyan transition-colors" />
                        </div>
                        <div className="grid grid-cols-2 gap-2 text-xs md:text-sm">
                          <div>
                            <span className="text-muted">거리:</span>{' '}
                            <span className="font-mono">{activity.distance_km} km</span>
                          </div>
                          <div>
                            <span className="text-muted">시간:</span>{' '}
                            <span className="font-mono">
                              {formatDurationSeconds(activity.duration_seconds)}
                            </span>
                          </div>
                          {activity.avg_hr && (
                            <div className="col-span-2">
                              <span className="text-muted">평균 심박:</span>{' '}
                              <span className="font-mono text-red-400">
                                {activity.avg_hr} bpm
                                {activity.avg_hr_percent != null && (
                                  <span className="text-muted ml-1">({activity.avg_hr_percent}%)</span>
                                )}
                              </span>
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
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

              {/* 대회 정보 */}
              {selectedRaceData && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <h4 className="text-xs font-medium text-muted uppercase tracking-wider flex items-center gap-1">
                      <Trophy className="w-3.5 h-3.5" />
                      대회
                    </h4>
                    <button
                      onClick={() => openRaceModal(selectedRaceData)}
                      className="text-xs text-amber hover:text-amber/80 flex items-center gap-1"
                    >
                      수정
                    </button>
                  </div>
                  <div className="p-3 rounded-lg bg-amber/10 border border-amber/30">
                    <div className="flex items-center gap-2 mb-2">
                      <Trophy className="w-4 h-4 text-amber" />
                      <span className="font-medium text-sm text-amber">{selectedRaceData.name}</span>
                      {selectedRaceData.is_primary && (
                        <Star className="w-3.5 h-3.5 text-amber fill-amber" />
                      )}
                    </div>
                    <div className="space-y-1 text-xs">
                      {selectedRaceData.distance_label && (
                        <div className="flex items-center gap-2">
                          <Flag className="w-3.5 h-3.5 text-muted" />
                          <span>{selectedRaceData.distance_label}</span>
                          {selectedRaceData.distance_km && (
                            <span className="text-muted">({selectedRaceData.distance_km}km)</span>
                          )}
                        </div>
                      )}
                      {selectedRaceData.location && (
                        <div className="flex items-center gap-2">
                          <MapPin className="w-3.5 h-3.5 text-muted" />
                          <span>{selectedRaceData.location}</span>
                        </div>
                      )}
                      {selectedRaceData.goal_time_seconds && (
                        <div className="flex items-center gap-2">
                          <Target className="w-3.5 h-3.5 text-cyan" />
                          <span>목표: <span className="font-mono text-cyan">{secondsToTimeString(selectedRaceData.goal_time_seconds)}</span></span>
                        </div>
                      )}
                      {selectedRaceData.goal_description && (
                        <div className="mt-2 text-muted text-xs">
                          {selectedRaceData.goal_description}
                        </div>
                      )}
                      <div className="mt-2 pt-2 border-t border-amber/20">
                        <span className="font-mono text-amber">
                          D{selectedRaceData.days_until === 0 ? '-DAY' : selectedRaceData.days_until > 0 ? `-${selectedRaceData.days_until}` : `+${Math.abs(selectedRaceData.days_until)}`}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* 메모 섹션 */}
              <div>
                <div className="flex items-center justify-between mb-2">
                  <h4 className="text-xs font-medium text-muted uppercase tracking-wider flex items-center gap-1">
                    <StickyNote className="w-3.5 h-3.5" />
                    메모
                  </h4>
                  {!isEditingNote && (
                    <button
                      onClick={startEditNote}
                      className="text-xs text-yellow-500 hover:text-yellow-400 flex items-center gap-1"
                    >
                      {selectedNoteData ? '수정' : '추가'}
                    </button>
                  )}
                </div>

                {isEditingNote ? (
                  <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30 space-y-3">
                    {/* 메모 타입 선택 */}
                    <div className="flex flex-wrap gap-1.5">
                      {NOTE_TYPES.map((type) => (
                        <button
                          key={type.value}
                          onClick={() => setNoteType(type.value)}
                          className={clsx(
                            'px-2 py-1 rounded text-xs flex items-center gap-1 transition-colors',
                            noteType === type.value
                              ? 'bg-yellow-500/30 text-yellow-400 border border-yellow-500/50'
                              : 'bg-[var(--color-bg-tertiary)] text-muted hover:text-foreground border border-transparent'
                          )}
                        >
                          <span>{type.icon}</span>
                          <span>{type.label}</span>
                        </button>
                      ))}
                    </div>

                    {/* 메모 내용 입력 */}
                    <textarea
                      value={noteContent}
                      onChange={(e) => setNoteContent(e.target.value)}
                      placeholder="메모를 입력하세요..."
                      className="w-full p-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm resize-none focus:outline-none focus:ring-2 focus:ring-yellow-500/50"
                      rows={3}
                    />

                    {/* 버튼 그룹 */}
                    <div className="flex items-center justify-between">
                      <div>
                        {selectedNoteData && (
                          <button
                            onClick={handleDeleteNote}
                            disabled={deleteNote.isPending}
                            className="text-xs text-red-400 hover:text-red-300 flex items-center gap-1"
                          >
                            <Trash2 className="w-3.5 h-3.5" />
                            삭제
                          </button>
                        )}
                      </div>
                      <div className="flex gap-2">
                        <button
                          onClick={cancelEditNote}
                          className="px-3 py-1.5 text-xs text-muted hover:text-foreground flex items-center gap-1"
                        >
                          <X className="w-3.5 h-3.5" />
                          취소
                        </button>
                        <button
                          onClick={handleSaveNote}
                          disabled={!noteContent.trim() || createOrUpdateNote.isPending}
                          className="px-3 py-1.5 text-xs bg-yellow-500/20 text-yellow-400 hover:bg-yellow-500/30 rounded flex items-center gap-1 disabled:opacity-50"
                        >
                          <Save className="w-3.5 h-3.5" />
                          저장
                        </button>
                      </div>
                    </div>
                  </div>
                ) : selectedNoteData ? (
                  <div className="p-3 rounded-lg bg-yellow-500/10 border border-yellow-500/30">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-lg">{selectedNoteData.icon || '📝'}</span>
                      <span className="text-xs text-yellow-500/80">
                        {NOTE_TYPES.find(t => t.value === selectedNoteData.note_type)?.label || '메모'}
                      </span>
                    </div>
                    <p className="text-sm whitespace-pre-wrap">{selectedNoteData.content}</p>
                  </div>
                ) : (
                  <div className="p-3 rounded-lg bg-[var(--color-bg-tertiary)] border border-dashed border-[var(--color-border)] text-center">
                    <p className="text-xs text-muted">메모가 없습니다</p>
                  </div>
                )}
              </div>

              {/* 데이터 없음 - 활동/운동이 없을 때만 표시 */}
              {selectedDateData.activities.length === 0 &&
                selectedDateData.scheduled_workouts.length === 0 &&
                selectedStrengthData.length === 0 &&
                !selectedNoteData && (
                  <div className="text-center py-4 text-muted">
                    <button className="btn btn-secondary text-sm">
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

      {/* 대회 등록/수정 모달 */}
      {isRaceModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* 백드롭 */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={closeRaceModal}
          />

          {/* 모달 */}
          <div className="relative w-full max-w-lg bg-[var(--color-bg-card)] rounded-xl border border-[var(--color-border)] shadow-2xl max-h-[90vh] overflow-y-auto">
            {/* 헤더 */}
            <div className="sticky top-0 flex items-center justify-between p-4 border-b border-[var(--color-border)] bg-[var(--color-bg-card)]">
              <h2 className="text-lg font-display font-bold flex items-center gap-2">
                <Trophy className="w-5 h-5 text-amber" />
                {editingRace ? '대회 수정' : '대회 등록'}
              </h2>
              <button
                onClick={closeRaceModal}
                className="p-1.5 rounded-lg hover:bg-[var(--color-bg-tertiary)] text-muted hover:text-foreground transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* 폼 */}
            <div className="p-4 space-y-4">
              {/* Garmin 예측 불러오기 버튼 */}
              {!editingRace && garminPredictions && garminPredictions.predictions.length > 0 && (
                <div className="p-3 rounded-lg bg-cyan/5 border border-cyan/20">
                  <button
                    type="button"
                    onClick={() => setShowGarminPredictions(!showGarminPredictions)}
                    className="w-full flex items-center justify-between text-sm"
                  >
                    <span className="flex items-center gap-2">
                      <Activity className="w-4 h-4 text-cyan" />
                      <span className="font-medium text-cyan">Garmin 예측 기록 불러오기</span>
                      {garminPredictions.vo2_max && (
                        <span className="text-xs text-muted">(VO2Max: {garminPredictions.vo2_max})</span>
                      )}
                    </span>
                    <ChevronRight className={clsx(
                      'w-4 h-4 text-cyan transition-transform',
                      showGarminPredictions && 'rotate-90'
                    )} />
                  </button>

                  {showGarminPredictions && (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs text-muted mb-2">
                        Garmin에서 VO2Max를 기반으로 예측한 기록입니다. 클릭하여 목표 기록으로 설정하세요.
                      </p>
                      {garminPredictions.predictions.map((prediction) => (
                        <button
                          key={prediction.distance}
                          type="button"
                          onClick={() => applyGarminPrediction(prediction)}
                          className="w-full flex items-center justify-between p-2 rounded-lg bg-[var(--color-bg-secondary)] hover:bg-[var(--color-bg-tertiary)] transition-colors text-left"
                        >
                          <span className="font-medium">{prediction.distance}</span>
                          <span className="flex items-center gap-3 text-sm">
                            <span className="font-mono text-cyan">{prediction.predicted_time_formatted}</span>
                            <span className="text-muted text-xs">({prediction.pace_per_km}/km)</span>
                          </span>
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* 대회명 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  대회명 <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={raceForm.name}
                  onChange={(e) => setRaceForm(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="예: 2025 서울마라톤"
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-amber/50"
                />
              </div>

              {/* 대회 날짜 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  대회 날짜 <span className="text-red-400">*</span>
                </label>
                <input
                  type="date"
                  value={raceForm.race_date}
                  onChange={(e) => setRaceForm(prev => ({ ...prev, race_date: e.target.value }))}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-amber/50"
                />
              </div>

              {/* 거리 선택 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">거리</label>
                <div className="flex flex-wrap gap-2">
                  {RACE_DISTANCES.map((dist) => (
                    <button
                      key={dist.label}
                      onClick={() => handleDistanceChange(dist.value, dist.label)}
                      className={clsx(
                        'px-3 py-1.5 rounded-lg text-sm transition-colors',
                        raceForm.distance_label === dist.label
                          ? 'bg-amber/20 text-amber border border-amber/50'
                          : 'bg-[var(--color-bg-tertiary)] text-muted hover:text-foreground border border-transparent'
                      )}
                    >
                      {dist.label}
                    </button>
                  ))}
                </div>
                {raceForm.distance_label === '기타' && (
                  <input
                    type="number"
                    value={raceForm.distance_km || ''}
                    onChange={(e) => setRaceForm(prev => ({ ...prev, distance_km: parseFloat(e.target.value) || 0 }))}
                    placeholder="거리 (km)"
                    className="mt-2 w-full px-3 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-amber/50"
                  />
                )}
              </div>

              {/* 장소 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">장소</label>
                <div className="relative">
                  <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
                  <input
                    type="text"
                    value={raceForm.location}
                    onChange={(e) => setRaceForm(prev => ({ ...prev, location: e.target.value }))}
                    placeholder="예: 서울 잠실"
                    className="w-full pl-10 pr-3 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm focus:outline-none focus:ring-2 focus:ring-amber/50"
                  />
                </div>
              </div>

              {/* 목표 기록 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">
                  <Target className="w-4 h-4 inline mr-1 text-cyan" />
                  목표 기록
                </label>
                <div className="flex items-center gap-2">
                  <div className="flex-1">
                    <input
                      type="number"
                      min="0"
                      max="23"
                      value={raceForm.goal_hours}
                      onChange={(e) => setRaceForm(prev => ({ ...prev, goal_hours: parseInt(e.target.value) || 0 }))}
                      placeholder="시"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm text-center focus:outline-none focus:ring-2 focus:ring-cyan/50"
                    />
                    <span className="block text-center text-xs text-muted mt-1">시간</span>
                  </div>
                  <span className="text-lg text-muted">:</span>
                  <div className="flex-1">
                    <input
                      type="number"
                      min="0"
                      max="59"
                      value={raceForm.goal_minutes}
                      onChange={(e) => setRaceForm(prev => ({ ...prev, goal_minutes: parseInt(e.target.value) || 0 }))}
                      placeholder="분"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm text-center focus:outline-none focus:ring-2 focus:ring-cyan/50"
                    />
                    <span className="block text-center text-xs text-muted mt-1">분</span>
                  </div>
                  <span className="text-lg text-muted">:</span>
                  <div className="flex-1">
                    <input
                      type="number"
                      min="0"
                      max="59"
                      value={raceForm.goal_seconds}
                      onChange={(e) => setRaceForm(prev => ({ ...prev, goal_seconds: parseInt(e.target.value) || 0 }))}
                      placeholder="초"
                      className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm text-center focus:outline-none focus:ring-2 focus:ring-cyan/50"
                    />
                    <span className="block text-center text-xs text-muted mt-1">초</span>
                  </div>
                </div>
              </div>

              {/* 목표 설명 */}
              <div>
                <label className="block text-sm font-medium mb-1.5">목표 설명</label>
                <textarea
                  value={raceForm.goal_description}
                  onChange={(e) => setRaceForm(prev => ({ ...prev, goal_description: e.target.value }))}
                  placeholder="예: 서브3 달성, 페이스 유지하며 완주"
                  rows={2}
                  className="w-full px-3 py-2 rounded-lg bg-[var(--color-bg-secondary)] border border-[var(--color-border)] text-sm resize-none focus:outline-none focus:ring-2 focus:ring-amber/50"
                />
              </div>

              {/* 주요 대회 설정 */}
              <div className="flex items-center gap-3 p-3 rounded-lg bg-amber/5 border border-amber/20">
                <input
                  type="checkbox"
                  id="is_primary"
                  checked={raceForm.is_primary}
                  onChange={(e) => setRaceForm(prev => ({ ...prev, is_primary: e.target.checked }))}
                  className="w-4 h-4 rounded border-amber/50 text-amber focus:ring-amber/50"
                />
                <label htmlFor="is_primary" className="flex-1 text-sm">
                  <span className="font-medium flex items-center gap-1">
                    <Star className="w-4 h-4 text-amber" />
                    주요 대회로 설정
                  </span>
                  <span className="block text-xs text-muted mt-0.5">
                    D-day 카운트다운에 표시됩니다
                  </span>
                </label>
              </div>
            </div>

            {/* 푸터 */}
            <div className="sticky bottom-0 flex items-center justify-between p-4 border-t border-[var(--color-border)] bg-[var(--color-bg-card)]">
              <div>
                {editingRace && (
                  <button
                    onClick={handleDeleteRace}
                    disabled={deleteRace.isPending}
                    className="px-4 py-2 text-sm text-red-400 hover:text-red-300 hover:bg-red-500/10 rounded-lg flex items-center gap-2 transition-colors"
                  >
                    <Trash2 className="w-4 h-4" />
                    삭제
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={closeRaceModal}
                  className="px-4 py-2 text-sm text-muted hover:text-foreground rounded-lg transition-colors"
                >
                  취소
                </button>
                <button
                  onClick={handleSaveRace}
                  disabled={!raceForm.name || !raceForm.race_date || createRace.isPending || updateRace.isPending}
                  className="px-4 py-2 text-sm bg-amber text-black font-medium rounded-lg hover:bg-amber/90 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 transition-colors"
                >
                  <Save className="w-4 h-4" />
                  {editingRace ? '수정' : '등록'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
