import { useState } from 'react';
import {
  ChevronLeft,
  ChevronRight,
  Activity,
  Dumbbell,
  Plus,
} from 'lucide-react';
import clsx from 'clsx';

// Mock data for calendar
const mockCalendarData: Record<string, { activities: Activity[]; workouts: Workout[] }> = {
  '2024-12-29': {
    activities: [{ id: 1, name: 'Morning Easy Run', type: 'running', distance: 8.2, duration: 46 }],
    workouts: [],
  },
  '2024-12-27': {
    activities: [{ id: 2, name: 'Tempo Run', type: 'running', distance: 10.0, duration: 48 }],
    workouts: [],
  },
  '2024-12-25': {
    activities: [],
    workouts: [{ id: 1, name: 'Recovery Run', type: 'easy', status: 'scheduled' }],
  },
  '2024-12-22': {
    activities: [{ id: 3, name: 'Long Run Sunday', type: 'running', distance: 21.1, duration: 117 }],
    workouts: [],
  },
  '2024-12-20': {
    activities: [{ id: 4, name: 'Recovery Jog', type: 'running', distance: 5.0, duration: 30 }],
    workouts: [],
  },
  '2024-12-18': {
    activities: [{ id: 5, name: 'Interval Training', type: 'running', distance: 8.5, duration: 40 }],
    workouts: [],
  },
  '2024-12-31': {
    activities: [],
    workouts: [{ id: 2, name: 'New Year Easy Run', type: 'easy', status: 'scheduled' }],
  },
  '2025-01-01': {
    activities: [],
    workouts: [{ id: 3, name: 'Base Building', type: 'steady', status: 'scheduled' }],
  },
  '2025-01-03': {
    activities: [],
    workouts: [{ id: 4, name: 'Tempo Session', type: 'tempo', status: 'scheduled' }],
  },
  '2025-01-05': {
    activities: [],
    workouts: [{ id: 5, name: 'Long Run', type: 'long', status: 'scheduled' }],
  },
};

interface Activity {
  id: number;
  name: string;
  type: string;
  distance: number;
  duration: number;
}

interface Workout {
  id: number;
  name: string;
  type: string;
  status: string;
}

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const MONTHS = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December',
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

export function Calendar() {
  const [currentDate, setCurrentDate] = useState(new Date());
  const [selectedDate, setSelectedDate] = useState<string | null>(null);

  const year = currentDate.getFullYear();
  const month = currentDate.getMonth();

  // Get first day of month and total days
  const firstDayOfMonth = new Date(year, month, 1);
  const lastDayOfMonth = new Date(year, month + 1, 0);
  const daysInMonth = lastDayOfMonth.getDate();

  // Get day of week for first day (0 = Sunday, adjust to Monday start)
  let startDay = firstDayOfMonth.getDay() - 1;
  if (startDay < 0) startDay = 6;

  // Generate calendar days
  const calendarDays: (number | null)[] = [];

  // Add empty slots for days before first of month
  for (let i = 0; i < startDay; i++) {
    calendarDays.push(null);
  }

  // Add days of the month
  for (let day = 1; day <= daysInMonth; day++) {
    calendarDays.push(day);
  }

  // Navigation
  const goToPreviousMonth = () => {
    setCurrentDate(new Date(year, month - 1, 1));
  };

  const goToNextMonth = () => {
    setCurrentDate(new Date(year, month + 1, 1));
  };

  const goToToday = () => {
    setCurrentDate(new Date());
  };

  // Get data for a specific date
  const getDateData = (day: number) => {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
    return mockCalendarData[dateStr] || { activities: [], workouts: [] };
  };

  // Check if date is today
  const isToday = (day: number) => {
    const today = new Date();
    return (
      day === today.getDate() &&
      month === today.getMonth() &&
      year === today.getFullYear()
    );
  };

  // Selected date data
  const selectedDateData = selectedDate ? mockCalendarData[selectedDate] : null;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">Calendar</h1>
          <p className="text-muted text-sm mt-1">View your training schedule</p>
        </div>
        <button className="btn btn-primary flex items-center gap-2">
          <Plus className="w-4 h-4" />
          Schedule Workout
        </button>
      </div>

      <div className="grid grid-cols-3 gap-6">
        {/* Calendar Grid */}
        <div className="col-span-2 card p-6">
          {/* Calendar Header */}
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-display font-bold">
              {MONTHS[month]} {year}
            </h2>
            <div className="flex items-center gap-2">
              <button onClick={goToToday} className="btn btn-secondary text-sm px-3 py-1">
                Today
              </button>
              <button
                onClick={goToPreviousMonth}
                className="btn btn-secondary p-2"
              >
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button
                onClick={goToNextMonth}
                className="btn btn-secondary p-2"
              >
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Weekday Headers */}
          <div className="grid grid-cols-7 gap-1 mb-2">
            {WEEKDAYS.map((day) => (
              <div
                key={day}
                className="text-center text-xs font-medium text-muted uppercase tracking-wider py-2"
              >
                {day}
              </div>
            ))}
          </div>

          {/* Calendar Days */}
          <div className="grid grid-cols-7 gap-1">
            {calendarDays.map((day, index) => {
              if (day === null) {
                return <div key={`empty-${index}`} className="h-24" />;
              }

              const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(day).padStart(2, '0')}`;
              const data = getDateData(day);
              const hasActivity = data.activities.length > 0;
              const hasWorkout = data.workouts.length > 0;
              const isSelected = selectedDate === dateStr;

              return (
                <button
                  key={day}
                  onClick={() => setSelectedDate(dateStr)}
                  className={clsx(
                    'h-24 p-2 rounded-lg border transition-all text-left',
                    'hover:border-cyan/30 hover:bg-[var(--color-bg-tertiary)]',
                    isSelected && 'border-cyan bg-cyan/5',
                    !isSelected && 'border-transparent',
                    isToday(day) && 'ring-2 ring-cyan/50'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <span
                      className={clsx(
                        'text-sm font-medium',
                        isToday(day) && 'text-cyan'
                      )}
                    >
                      {day}
                    </span>
                    {(hasActivity || hasWorkout) && (
                      <div className="flex gap-1">
                        {hasActivity && (
                          <div className="w-2 h-2 rounded-full bg-cyan" />
                        )}
                        {hasWorkout && (
                          <div className="w-2 h-2 rounded-full bg-amber" />
                        )}
                      </div>
                    )}
                  </div>

                  {/* Activity/Workout Preview */}
                  <div className="mt-1 space-y-1">
                    {data.activities.slice(0, 1).map((activity) => (
                      <div
                        key={activity.id}
                        className="text-xs truncate text-cyan/80 flex items-center gap-1"
                      >
                        <Activity className="w-3 h-3" />
                        {activity.distance}km
                      </div>
                    ))}
                    {data.workouts.slice(0, 1).map((workout) => (
                      <div
                        key={workout.id}
                        className={clsx(
                          'text-xs truncate px-1 py-0.5 rounded border',
                          getWorkoutTypeColor(workout.type)
                        )}
                      >
                        {workout.name}
                      </div>
                    ))}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Legend */}
          <div className="flex items-center gap-6 mt-6 pt-4 border-t border-[var(--color-border)]">
            <div className="flex items-center gap-2 text-sm text-muted">
              <div className="w-3 h-3 rounded-full bg-cyan" />
              <span>Completed Activity</span>
            </div>
            <div className="flex items-center gap-2 text-sm text-muted">
              <div className="w-3 h-3 rounded-full bg-amber" />
              <span>Scheduled Workout</span>
            </div>
          </div>
        </div>

        {/* Day Details Panel */}
        <div className="card p-6">
          <h3 className="text-lg font-display font-bold mb-4">
            {selectedDate
              ? new Date(selectedDate).toLocaleDateString('en-US', {
                  weekday: 'long',
                  month: 'long',
                  day: 'numeric',
                })
              : 'Select a Day'}
          </h3>

          {selectedDateData ? (
            <div className="space-y-4">
              {/* Activities */}
              {selectedDateData.activities.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-muted uppercase tracking-wider mb-2">
                    Activities
                  </h4>
                  {selectedDateData.activities.map((activity) => (
                    <div
                      key={activity.id}
                      className="p-3 rounded-lg bg-[var(--color-bg-tertiary)] border border-cyan/20"
                    >
                      <div className="flex items-center gap-2 mb-2">
                        <Activity className="w-4 h-4 text-cyan" />
                        <span className="font-medium">{activity.name}</span>
                      </div>
                      <div className="grid grid-cols-2 gap-2 text-sm">
                        <div>
                          <span className="text-muted">Distance:</span>{' '}
                          <span className="font-mono">{activity.distance} km</span>
                        </div>
                        <div>
                          <span className="text-muted">Duration:</span>{' '}
                          <span className="font-mono">{activity.duration} min</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* Scheduled Workouts */}
              {selectedDateData.workouts.length > 0 && (
                <div>
                  <h4 className="text-sm font-medium text-muted uppercase tracking-wider mb-2">
                    Scheduled Workouts
                  </h4>
                  {selectedDateData.workouts.map((workout) => (
                    <div
                      key={workout.id}
                      className={clsx(
                        'p-3 rounded-lg border',
                        getWorkoutTypeColor(workout.type)
                      )}
                    >
                      <div className="flex items-center gap-2">
                        <Dumbbell className="w-4 h-4" />
                        <span className="font-medium">{workout.name}</span>
                      </div>
                      <div className="mt-1 text-xs opacity-80">
                        Type: {workout.type} | Status: {workout.status}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              {/* No Data */}
              {selectedDateData.activities.length === 0 &&
                selectedDateData.workouts.length === 0 && (
                  <div className="text-center py-8 text-muted">
                    <p>No activities or workouts</p>
                    <button className="btn btn-secondary mt-4 text-sm">
                      Schedule Workout
                    </button>
                  </div>
                )}
            </div>
          ) : (
            <div className="text-center py-12 text-muted">
              <p>Click on a day to see details</p>
            </div>
          )}
        </div>
      </div>

      {/* Upcoming Workouts */}
      <div className="card p-6">
        <h3 className="text-lg font-display font-bold mb-4">Upcoming Workouts</h3>
        <div className="grid grid-cols-4 gap-4">
          {Object.entries(mockCalendarData)
            .filter(([_, data]) => data.workouts.length > 0)
            .sort(([a], [b]) => a.localeCompare(b))
            .slice(0, 4)
            .map(([dateStr, data]) => (
              <div
                key={dateStr}
                className="p-4 rounded-lg bg-[var(--color-bg-tertiary)] border border-[var(--color-border)]"
              >
                <p className="text-xs text-muted mb-2">
                  {new Date(dateStr).toLocaleDateString('en-US', {
                    weekday: 'short',
                    month: 'short',
                    day: 'numeric',
                  })}
                </p>
                {data.workouts.map((workout) => (
                  <div key={workout.id}>
                    <p className="font-medium">{workout.name}</p>
                    <span
                      className={clsx(
                        'text-xs px-2 py-0.5 rounded mt-1 inline-block',
                        getWorkoutTypeColor(workout.type)
                      )}
                    >
                      {workout.type}
                    </span>
                  </div>
                ))}
              </div>
            ))}
        </div>
      </div>
    </div>
  );
}
