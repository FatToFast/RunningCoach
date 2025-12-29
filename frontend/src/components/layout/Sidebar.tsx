import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  TrendingUp,
  Trophy,
  Calendar,
  MessageSquare,
  Dumbbell,
  Heart,
} from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/activities', icon: Activity, label: 'Activities' },
  { to: '/trends', icon: TrendingUp, label: 'Trends' },
  { to: '/records', icon: Trophy, label: 'Records' },
  { to: '/calendar', icon: Calendar, label: 'Calendar' },
  { to: '/workouts', icon: Dumbbell, label: 'Workouts' },
  { to: '/health', icon: Heart, label: 'Health' },
  { to: '/ai', icon: MessageSquare, label: 'AI Coach' },
];

export function Sidebar() {
  return (
    <aside className="fixed left-0 top-16 bottom-0 w-64 bg-[var(--color-bg-secondary)] border-r border-[var(--color-border)] overflow-y-auto">
      <nav className="p-4 space-y-1">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              clsx(
                'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all',
                isActive
                  ? 'bg-[var(--color-accent-cyan)]/10 text-cyan border border-[var(--color-accent-cyan)]/30'
                  : 'text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-tertiary)]'
              )
            }
          >
            <Icon className="w-5 h-5" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Quick Actions */}
      <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-[var(--color-border)] bg-[var(--color-bg-secondary)]">
        <button className="btn btn-primary w-full">
          <MessageSquare className="w-4 h-4" />
          Ask AI Coach
        </button>
      </div>
    </aside>
  );
}
