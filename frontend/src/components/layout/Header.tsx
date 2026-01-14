import { useState, useRef, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Settings, User as UserIcon, RefreshCw, Menu, LogOut, Loader2 } from 'lucide-react';
import clsx from 'clsx';
import { useLogout } from '../../hooks/useAuth';
import { useGarminSyncStatus, useGarminSync } from '../../hooks/useGarminSync';
import type { User } from '../../api/auth';

export interface HeaderProps {
  onMenuToggle?: () => void;
  user?: User;
}

export function Header({ onMenuToggle, user }: HeaderProps) {
  const [showUserMenu, setShowUserMenu] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const logout = useLogout();

  // Garmin sync hooks
  const { data: garminStatus } = useGarminSyncStatus();
  const syncMutation = useGarminSync();

  const isConnected = garminStatus?.connected ?? false;
  const isSyncing = garminStatus?.running || syncMutation.isPending;
  // Sort by timestamp (ISO format sorts correctly as strings, but use Date for safety)
  const lastSync = garminStatus?.sync_states
    ?.map((s) => s.last_success_at)
    .filter((d): d is string => Boolean(d))
    .sort((a, b) => new Date(b).getTime() - new Date(a).getTime())?.[0];

  // 헤더의 동기화 버튼은 "빠른 동기화" - 최근 7일간 activities만
  const handleQuickSync = () => {
    if (!isSyncing && isConnected) {
      const today = new Date();
      const weekAgo = new Date(today);
      weekAgo.setDate(weekAgo.getDate() - 7);

      syncMutation.mutate({
        endpoints: ['activities'],  // activities만 동기화
        start_date: weekAgo.toISOString().split('T')[0],
        end_date: today.toISOString().split('T')[0],
      });
    }
  };

  // Close menu on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setShowUserMenu(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleLogout = async () => {
    try {
      await logout.mutateAsync();
      navigate('/login');
    } catch (err) {
      console.error('Logout failed:', err);
    }
  };

  return (
    <header className="fixed top-0 left-0 right-0 z-50 bg-[var(--color-bg-elevated)]/95 backdrop-blur border-b border-[var(--color-border)] shadow-sm">
      <div className="h-16 px-4 lg:px-6 flex items-center justify-between">
        {/* Mobile Menu & Logo */}
        <div className="flex items-center gap-3">
          {/* Mobile menu button */}
          <button
            className="lg:hidden btn btn-secondary p-2"
            onClick={onMenuToggle}
            aria-label="메뉴 열기"
            title="메뉴 열기"
          >
            <Menu className="w-5 h-5" />
          </button>

          <h1 className="font-display text-xl font-semibold tracking-tight text-ink">
            Running<span className="text-accent">Coach</span>
          </h1>

          {/* Connection Status & Sync Button */}
          <div className="flex items-center gap-3 ml-4 md:ml-6 pl-4 md:pl-6 border-l border-[var(--color-border)]">
            {isConnected ? (
              <>
                <span className="badge badge-live hidden sm:inline-flex">GARMIN</span>
                {lastSync && (
                  <span className="text-xs text-secondary hidden lg:inline">
                    {new Date(lastSync).toLocaleTimeString()}
                  </span>
                )}
                <button
                  onClick={handleQuickSync}
                  disabled={isSyncing}
                  className={clsx(
                    'btn btn-primary p-1.5 md:px-3 text-xs flex items-center gap-1.5',
                    isSyncing && 'opacity-70 cursor-not-allowed'
                  )}
                  aria-label={isSyncing ? '동기화 중' : '최근 활동 동기화'}
                  title={isSyncing ? '동기화 중...' : '최근 7일 활동 동기화 (전체 동기화는 설정에서)'}
                >
                  {isSyncing ? (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  ) : (
                    <RefreshCw className="w-4 h-4" />
                  )}
                  <span className="hidden md:inline">
                    {isSyncing ? '동기화 중' : '새 활동'}
                  </span>
                </button>
              </>
            ) : (
              <Link
                to="/settings"
                className="text-xs text-warning hover:text-accent-strong flex items-center gap-1 font-medium"
              >
                <span className="hidden sm:inline">Garmin 연결 필요</span>
                <span className="sm:hidden">연결</span>
              </Link>
            )}
          </div>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          <Link
            to="/settings"
            className="btn btn-secondary p-2"
            aria-label="설정"
            title="설정"
          >
            <Settings className="w-5 h-5" />
          </Link>

          {/* User Menu */}
          <div className="relative" ref={menuRef}>
            <button
              className="btn btn-secondary p-2 flex items-center gap-2"
              onClick={() => setShowUserMenu(!showUserMenu)}
              aria-label="사용자 메뉴"
              aria-expanded={showUserMenu}
              aria-haspopup="true"
              title="프로필"
            >
              <UserIcon className="w-5 h-5" />
              {user && (
                <span className="hidden sm:inline text-sm max-w-[100px] truncate">
                  {user.display_name || user.email?.split('@')[0] || 'User'}
                </span>
              )}
            </button>

            {/* Dropdown */}
            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-[var(--color-bg-elevated)] border border-[var(--color-border)] rounded-lg shadow-lg overflow-hidden">
                {user && (
                  <div className="px-4 py-3 border-b border-[var(--color-border)]">
                    <p className="text-sm font-medium truncate">
                      {user.display_name || 'User'}
                    </p>
                    <p className="text-xs text-muted truncate">{user.email || ''}</p>
                  </div>
                )}
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2.5 text-left text-sm text-danger hover:bg-[var(--color-bg-secondary)] flex items-center gap-2 transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  로그아웃
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  );
}
