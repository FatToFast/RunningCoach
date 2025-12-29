import { Activity, Settings, User, RefreshCw } from 'lucide-react';

interface HeaderProps {
  lastSync?: string | null;
  isConnected?: boolean;
}

export function Header({ lastSync, isConnected = false }: HeaderProps) {
  return (
    <header className="sticky top-0 z-50 bg-[var(--color-bg-secondary)] border-b border-[var(--color-border)]">
      <div className="max-w-[1920px] mx-auto px-6 h-16 flex items-center justify-between">
        {/* Logo & Title */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Activity className="w-8 h-8 text-cyan" />
            <h1 className="font-display text-xl font-bold tracking-tight">
              RUNNING<span className="text-cyan">COACH</span>
            </h1>
          </div>

          {/* Connection Status */}
          <div className="flex items-center gap-3 ml-6 pl-6 border-l border-[var(--color-border)]">
            {isConnected && (
              <span className="badge badge-live">LIVE</span>
            )}
            {lastSync && (
              <span className="text-xs text-muted flex items-center gap-1">
                <RefreshCw className="w-3 h-3" />
                Last sync: {new Date(lastSync).toLocaleTimeString()}
              </span>
            )}
          </div>
        </div>

        {/* Right Actions */}
        <div className="flex items-center gap-2">
          <button className="btn btn-secondary p-2" title="Settings">
            <Settings className="w-5 h-5" />
          </button>
          <button className="btn btn-secondary p-2" title="Profile">
            <User className="w-5 h-5" />
          </button>
        </div>
      </div>
    </header>
  );
}
