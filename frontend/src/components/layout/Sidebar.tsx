import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Activity,
  TrendingUp,
  Trophy,
  Calendar,
  MessageSquare,
  Dumbbell,
  Footprints,
  X,
  ClipboardList,
} from 'lucide-react';
import clsx from 'clsx';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: '대시보드' },
  { to: '/activities', icon: Activity, label: '활동' },
  { to: '/trends', icon: TrendingUp, label: '트렌드' },
  { to: '/records', icon: Trophy, label: '기록' },
  { to: '/calendar', icon: Calendar, label: '캘린더' },
  { to: '/gear', icon: Footprints, label: '신발 관리' },
  { to: '/strength', icon: Dumbbell, label: '보강운동' },
  { to: '/workouts', icon: ClipboardList, label: '워크아웃' },
  { to: '/ai', icon: MessageSquare, label: 'AI 코치' },
];

interface SidebarProps {
  isOpen?: boolean;
  onClose?: () => void;
}

export function Sidebar({ isOpen = false, onClose }: SidebarProps) {
  const navigate = useNavigate();

  const handleAICoachClick = () => {
    onClose?.();
    navigate('/ai');
  };

  return (
    <>
      {/* Mobile Overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={clsx(
          'fixed top-16 bottom-0 w-64 bg-[var(--color-bg-elevated)] border-r border-[var(--color-border)] overflow-y-auto z-40 transition-transform duration-300',
          // Desktop: always visible
          'lg:left-0 lg:translate-x-0',
          // Mobile: slide in/out
          isOpen ? 'left-0 translate-x-0' : '-translate-x-full lg:translate-x-0'
        )}
      >
        {/* Mobile close button */}
        <div className="lg:hidden flex justify-end p-2 border-b border-[var(--color-border)]">
          <button
            className="btn btn-secondary p-2"
            onClick={onClose}
            aria-label="메뉴 닫기"
            title="메뉴 닫기"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <nav className="p-4 space-y-1">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              onClick={onClose}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all',
                  isActive
                    ? 'bg-[var(--color-accent-soft)] text-accent-strong border border-[var(--color-border-accent)]'
                    : 'text-secondary hover:text-ink hover:bg-[var(--color-bg-secondary)]'
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
          <button
            onClick={handleAICoachClick}
            className="btn btn-primary w-full"
            aria-label="AI 코치 페이지로 이동"
          >
            <MessageSquare className="w-4 h-4" />
            AI 코치에게 질문
          </button>
        </div>
      </aside>
    </>
  );
}
