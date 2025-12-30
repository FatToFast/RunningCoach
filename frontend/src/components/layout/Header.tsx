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
  const lastSync = garminStatus?.sync_states
    ?.map((s) => s.last_success_at)
    .filter(Boolean)
    .sort()
    .pop();

  const handleSync = () => {
    if (!isSyncing && isConnected) {
      syncMutation.mutate();
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
    <header className="fixed top-0 left-0 right-0 z-50 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)]">
      <div className="h-16 px-4 lg:px-6 flex items-center justify-between">
        {/* Mobile Menu & Logo */}
        <div className="flex items-center gap-3">
          {/* Mobile menu button */}
          <button
            className="lg:hidden btn btn-secondary p-2"
            onClick={onMenuToggle}
            title="Menu"
          >
            <Menu className="w-5 h-5" />
          </button>

          <h1 className="font-display text-xl font-bold tracking-tight">
            RUNNING<span className="text-cyan">COACH</span>
          </h1>

          {/* Connection Status & Sync Button - hidden on mobile */}
          <div className="hidden md:flex items-center gap-3 ml-6 pl-6 border-l border-[var(--color-border)]">
            {isConnected ? (
              <>
                <span className="badge badge-live">GARMIN</span>
                {lastSync && (
                  <span className="text-xs text-muted">
                    {new Date(lastSync).toLocaleTimeString()}
                  </span>
                )}
                <button
                  onClick={handleSync}
                  disabled={isSyncing}
                  className={clsx(
                    'btn btn-secondary p-1.5 text-xs flex items-center gap-1.5',
                    isSyncing && 'opacity-70 cursor-not-allowed'
                  )}
                  title={isSyncing ? '동기화 중...' : 'Garmin 동기화'}
                >
                  {isSyncing ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <RefreshCw className="w-3.5 h-3.5" />
                  )}
                  <span className="hidden lg:inline">
                    {isSyncing ? '동기화 중' : '동기화'}
                  </span>
                </button>
              </>
            ) : (
              <Link
                to="/settings"
                className="text-xs text-amber hover:text-amber/80 flex items-center gap-1"
              >
                Garmin 연결 필요
              </Link>
            )}
          </div>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          <Link to="/settings" className="btn btn-secondary p-2" title="Settings">
            <Settings className="w-5 h-5" />
          </Link>

          {/* User Menu */}
          <div className="relative" ref={menuRef}>
            <button
              className="btn btn-secondary p-2 flex items-center gap-2"
              onClick={() => setShowUserMenu(!showUserMenu)}
              title="Profile"
            >
              <UserIcon className="w-5 h-5" />
              {user && (
                <span className="hidden sm:inline text-sm max-w-[100px] truncate">
                  {user.display_name || user.email.split('@')[0]}
                </span>
              )}
            </button>

            {/* Dropdown */}
            {showUserMenu && (
              <div className="absolute right-0 mt-2 w-48 bg-[var(--color-bg-secondary)] border border-[var(--color-border)] rounded-lg shadow-lg overflow-hidden">
                {user && (
                  <div className="px-4 py-3 border-b border-[var(--color-border)]">
                    <p className="text-sm font-medium truncate">
                      {user.display_name || 'User'}
                    </p>
                    <p className="text-xs text-muted truncate">{user.email}</p>
                  </div>
                )}
                <button
                  onClick={handleLogout}
                  className="w-full px-4 py-2.5 text-left text-sm text-red-400 hover:bg-[var(--color-bg-tertiary)] flex items-center gap-2 transition-colors"
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
