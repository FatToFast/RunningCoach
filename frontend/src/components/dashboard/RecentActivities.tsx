import { Activity, Clock, Heart, ArrowRight } from 'lucide-react';
import { Link } from 'react-router-dom';
import type { RecentActivity } from '../../types/api';

interface RecentActivitiesProps {
  activities: RecentActivity[];
}

export function RecentActivities({ activities }: RecentActivitiesProps) {
  if (!activities.length) {
    return (
      <div className="card">
        <h3 className="font-display text-lg font-semibold mb-4">Recent Activities</h3>
        <p className="text-muted text-sm">No recent activities found.</p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-display text-lg font-semibold">Recent Activities</h3>
        <Link to="/activities" className="text-cyan text-sm hover:underline flex items-center gap-1">
          View all <ArrowRight className="w-4 h-4" />
        </Link>
      </div>

      <div className="space-y-3">
        {activities.map((activity) => (
          <Link
            key={activity.id}
            to={`/activities/${activity.id}`}
            className="flex items-center gap-4 p-3 -mx-3 rounded-lg hover:bg-[var(--color-bg-tertiary)] transition-colors"
          >
            <div className="w-10 h-10 rounded-full bg-[var(--color-accent-cyan)]/10 flex items-center justify-center">
              <Activity className="w-5 h-5 text-cyan" />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-medium truncate">
                  {activity.name || activity.activity_type}
                </span>
                <span className="text-xs text-muted bg-[var(--color-bg-tertiary)] px-2 py-0.5 rounded">
                  {activity.activity_type}
                </span>
              </div>
              <div className="text-sm text-muted flex items-center gap-3 mt-1">
                <span>
                  {new Date(activity.start_time).toLocaleDateString('ko-KR', {
                    month: 'short',
                    day: 'numeric',
                  })}
                </span>
                {activity.distance_km && (
                  <span>{activity.distance_km.toFixed(2)} km</span>
                )}
                {activity.duration_minutes && (
                  <span className="flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {activity.duration_minutes} min
                  </span>
                )}
              </div>
            </div>

            {activity.avg_hr && (
              <div className="flex items-center gap-1 text-sm">
                <Heart className="w-4 h-4 text-red" />
                <span className="font-mono">{activity.avg_hr}</span>
              </div>
            )}
          </Link>
        ))}
      </div>
    </div>
  );
}
