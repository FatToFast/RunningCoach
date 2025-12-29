import { useState } from 'react';
import {
  Activity,
  Clock,
  MapPin,
  Heart,
  Flame,
  TrendingUp,
  ChevronRight,
  Filter,
  Search,
  Calendar,
} from 'lucide-react';

// Mock data for activities
const mockActivities = [
  {
    id: 1,
    name: 'Morning Easy Run',
    type: 'running',
    date: '2024-12-29',
    startTime: '06:30',
    distance: 8.2,
    duration: 2760, // 46 min
    pace: '5:37',
    avgHr: 142,
    maxHr: 158,
    calories: 520,
    elevation: 45,
    cadence: 172,
  },
  {
    id: 2,
    name: 'Tempo Run',
    type: 'running',
    date: '2024-12-27',
    startTime: '17:00',
    distance: 10.0,
    duration: 2880, // 48 min
    pace: '4:48',
    avgHr: 165,
    maxHr: 178,
    calories: 680,
    elevation: 32,
    cadence: 178,
  },
  {
    id: 3,
    name: 'Long Run Sunday',
    type: 'running',
    date: '2024-12-22',
    startTime: '07:00',
    distance: 21.1,
    duration: 7020, // 1h 57m
    pace: '5:32',
    avgHr: 148,
    maxHr: 165,
    calories: 1420,
    elevation: 120,
    cadence: 170,
  },
  {
    id: 4,
    name: 'Recovery Jog',
    type: 'running',
    date: '2024-12-20',
    startTime: '18:30',
    distance: 5.0,
    duration: 1800, // 30 min
    pace: '6:00',
    avgHr: 128,
    maxHr: 142,
    calories: 310,
    elevation: 15,
    cadence: 165,
  },
  {
    id: 5,
    name: 'Interval Training',
    type: 'running',
    date: '2024-12-18',
    startTime: '06:00',
    distance: 8.5,
    duration: 2400, // 40 min
    pace: '4:42',
    avgHr: 172,
    maxHr: 188,
    calories: 620,
    elevation: 25,
    cadence: 182,
  },
  {
    id: 6,
    name: 'Hill Repeats',
    type: 'running',
    date: '2024-12-15',
    startTime: '07:30',
    distance: 7.2,
    duration: 2520, // 42 min
    pace: '5:50',
    avgHr: 158,
    maxHr: 182,
    calories: 540,
    elevation: 180,
    cadence: 168,
  },
];

function formatDuration(seconds: number): string {
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (hours > 0) {
    return `${hours}h ${minutes}m`;
  }
  return `${minutes}m`;
}

function formatDate(dateStr: string): string {
  const date = new Date(dateStr);
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) {
    return 'Today';
  }
  if (date.toDateString() === yesterday.toDateString()) {
    return 'Yesterday';
  }
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
}

function getActivityTypeColor(type: string): string {
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

function getPaceZone(pace: string): { label: string; color: string } {
  const [min, sec] = pace.split(':').map(Number);
  const totalSeconds = min * 60 + sec;

  if (totalSeconds < 270) return { label: 'Speed', color: 'text-red-400' };
  if (totalSeconds < 300) return { label: 'Tempo', color: 'text-amber' };
  if (totalSeconds < 360) return { label: 'Steady', color: 'text-green-400' };
  return { label: 'Easy', color: 'text-cyan' };
}

export function Activities() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<string>('all');

  const filteredActivities = mockActivities.filter((activity) => {
    const matchesSearch = activity.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = selectedType === 'all' || activity.type === selectedType;
    return matchesSearch && matchesType;
  });

  // Calculate summary stats
  const totalDistance = filteredActivities.reduce((sum, a) => sum + a.distance, 0);
  const totalDuration = filteredActivities.reduce((sum, a) => sum + a.duration, 0);
  const totalCalories = filteredActivities.reduce((sum, a) => sum + a.calories, 0);

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-display font-bold">Activities</h1>
          <p className="text-muted text-sm mt-1">
            {filteredActivities.length} activities found
          </p>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-4 gap-4">
        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-cyan/10 flex items-center justify-center">
              <MapPin className="w-5 h-5 text-cyan" />
            </div>
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Total Distance</p>
              <p className="text-xl font-mono font-bold">{totalDistance.toFixed(1)} km</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-amber/10 flex items-center justify-center">
              <Clock className="w-5 h-5 text-amber" />
            </div>
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Total Time</p>
              <p className="text-xl font-mono font-bold">{formatDuration(totalDuration)}</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-red-500/10 flex items-center justify-center">
              <Flame className="w-5 h-5 text-red-400" />
            </div>
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Calories</p>
              <p className="text-xl font-mono font-bold">{totalCalories.toLocaleString()}</p>
            </div>
          </div>
        </div>

        <div className="card p-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <Activity className="w-5 h-5 text-green-400" />
            </div>
            <div>
              <p className="text-xs text-muted uppercase tracking-wider">Activities</p>
              <p className="text-xl font-mono font-bold">{filteredActivities.length}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex items-center gap-4">
          {/* Search */}
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
            <input
              type="text"
              placeholder="Search activities..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-10 pr-4 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-cyan"
            />
          </div>

          {/* Type Filter */}
          <div className="flex items-center gap-2">
            <Filter className="w-4 h-4 text-muted" />
            <select
              value={selectedType}
              onChange={(e) => setSelectedType(e.target.value)}
              className="px-3 py-2 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-sm focus:outline-none focus:border-cyan"
            >
              <option value="all">All Types</option>
              <option value="running">Running</option>
              <option value="cycling">Cycling</option>
              <option value="swimming">Swimming</option>
            </select>
          </div>

          {/* Date Range */}
          <button className="btn btn-secondary flex items-center gap-2">
            <Calendar className="w-4 h-4" />
            Last 30 days
          </button>
        </div>
      </div>

      {/* Activity List */}
      <div className="space-y-3">
        {filteredActivities.map((activity) => {
          const paceZone = getPaceZone(activity.pace);

          return (
            <div
              key={activity.id}
              className="card p-4 hover:border-cyan/30 transition-all cursor-pointer group"
            >
              <div className="flex items-center gap-6">
                {/* Activity Icon */}
                <div className="w-12 h-12 rounded-xl bg-[var(--color-bg-tertiary)] flex items-center justify-center">
                  <Activity className={`w-6 h-6 ${getActivityTypeColor(activity.type)}`} />
                </div>

                {/* Main Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-3">
                    <h3 className="font-medium truncate">{activity.name}</h3>
                    <span className={`text-xs font-medium px-2 py-0.5 rounded ${paceZone.color} bg-current/10`}>
                      {paceZone.label}
                    </span>
                  </div>
                  <div className="flex items-center gap-4 mt-1 text-sm text-muted">
                    <span>{formatDate(activity.date)}</span>
                    <span>{activity.startTime}</span>
                  </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-5 gap-8 text-center">
                  <div>
                    <p className="text-xs text-muted uppercase tracking-wider mb-1">Distance</p>
                    <p className="font-mono font-bold">{activity.distance} km</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted uppercase tracking-wider mb-1">Duration</p>
                    <p className="font-mono font-bold">{formatDuration(activity.duration)}</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted uppercase tracking-wider mb-1">Pace</p>
                    <p className="font-mono font-bold text-cyan">{activity.pace}/km</p>
                  </div>
                  <div>
                    <p className="text-xs text-muted uppercase tracking-wider mb-1">Avg HR</p>
                    <p className="font-mono font-bold flex items-center justify-center gap-1">
                      <Heart className="w-3 h-3 text-red-400" />
                      {activity.avgHr}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-muted uppercase tracking-wider mb-1">Elevation</p>
                    <p className="font-mono font-bold flex items-center justify-center gap-1">
                      <TrendingUp className="w-3 h-3 text-green-400" />
                      {activity.elevation}m
                    </p>
                  </div>
                </div>

                {/* Arrow */}
                <ChevronRight className="w-5 h-5 text-muted group-hover:text-cyan transition-colors" />
              </div>
            </div>
          );
        })}
      </div>

      {/* Pagination placeholder */}
      {filteredActivities.length > 0 && (
        <div className="flex items-center justify-center gap-2 pt-4">
          <button className="btn btn-secondary px-4 py-2 text-sm" disabled>
            Previous
          </button>
          <span className="text-sm text-muted px-4">Page 1 of 1</span>
          <button className="btn btn-secondary px-4 py-2 text-sm" disabled>
            Next
          </button>
        </div>
      )}
    </div>
  );
}
