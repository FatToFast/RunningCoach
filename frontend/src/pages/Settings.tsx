import { useState } from 'react';
import { Link2, Link2Off, RefreshCw, AlertCircle, CheckCircle2, User, Watch, Download, Loader2 } from 'lucide-react';
import { useGarminStatus, useConnectGarmin, useDisconnectGarmin, useUser } from '../hooks/useAuth';
import { useGarminSync, useGarminSyncStatus } from '../hooks/useGarminSync';

export function Settings() {
  const { data: user } = useUser();
  const { data: garminStatus, isLoading: garminLoading } = useGarminStatus();
  const { data: syncStatus } = useGarminSyncStatus();
  const connectGarmin = useConnectGarmin();
  const disconnectGarmin = useDisconnectGarmin();
  const syncMutation = useGarminSync();

  const [garminEmail, setGarminEmail] = useState('');
  const [garminPassword, setGarminPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const isSyncing = syncMutation.isPending || syncStatus?.running;
  const canSync = garminStatus?.session_valid && !isSyncing;

  const handleConnect = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccess(null);

    if (!garminEmail || !garminPassword) {
      setError('Garmin 이메일과 비밀번호를 입력해주세요.');
      return;
    }

    try {
      await connectGarmin.mutateAsync({
        email: garminEmail,
        password: garminPassword,
      });
      setSuccess('Garmin Connect 연동이 완료되었습니다.');
      setGarminEmail('');
      setGarminPassword('');
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        'Garmin 연동에 실패했습니다.';
      setError(message);
    }
  };

  const handleDisconnect = async () => {
    if (!confirm('Garmin 연동을 해제하시겠습니까?')) return;

    setError(null);
    setSuccess(null);

    try {
      await disconnectGarmin.mutateAsync();
      setSuccess('Garmin 연동이 해제되었습니다.');
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '연동 해제에 실패했습니다.';
      setError(message);
    }
  };

  const handleFullSync = async () => {
    if (!confirm('전체 히스토리를 다시 동기화합니다. 시간이 오래 걸릴 수 있습니다. 계속하시겠습니까?')) return;

    setError(null);
    setSuccess(null);

    try {
      const result = await syncMutation.mutateAsync({ full_backfill: true });
      if (result.started) {
        setSuccess('전체 동기화가 시작되었습니다. 백그라운드에서 진행됩니다.');
      } else {
        setError(result.message || '동기화를 시작할 수 없습니다.');
      }
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '동기화 시작에 실패했습니다.';
      setError(message);
    }
  };

  const handleIncrementalSync = async () => {
    setError(null);
    setSuccess(null);

    // 새 데이터 동기화: 최근 30일 데이터만 (full_backfill: false)
    const today = new Date();
    const monthAgo = new Date(today);
    monthAgo.setDate(monthAgo.getDate() - 30);

    try {
      const result = await syncMutation.mutateAsync({
        full_backfill: false,
        start_date: monthAgo.toISOString().split('T')[0],
        end_date: today.toISOString().split('T')[0],
      });
      if (result.started) {
        setSuccess('새 데이터 동기화가 시작되었습니다. (최근 30일)');
      } else {
        setError(result.message || '동기화를 시작할 수 없습니다.');
      }
    } catch (err: unknown) {
      const message =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail ||
        '동기화 시작에 실패했습니다.';
      setError(message);
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleString('ko-KR');
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="font-display text-2xl font-bold">설정</h1>
        <p className="text-muted text-sm mt-1">계정 및 연동 서비스 관리</p>
      </div>

      {/* User Info */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-cyan/10 rounded-lg">
            <User className="w-5 h-5 text-cyan" />
          </div>
          <h2 className="font-display text-lg font-semibold">계정 정보</h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <label className="block text-sm text-muted mb-1">이메일</label>
            <p className="text-[var(--color-text-primary)]">{user?.email || '-'}</p>
          </div>
          <div>
            <label className="block text-sm text-muted mb-1">이름</label>
            <p className="text-[var(--color-text-primary)]">{user?.display_name || '-'}</p>
          </div>
          <div>
            <label className="block text-sm text-muted mb-1">타임존</label>
            <p className="text-[var(--color-text-primary)]">{user?.timezone || 'Asia/Seoul'}</p>
          </div>
        </div>
      </div>

      {/* Garmin Connect */}
      <div className="card p-6">
        <div className="flex items-center gap-3 mb-4">
          <div className="p-2 bg-orange-500/10 rounded-lg">
            <Watch className="w-5 h-5 text-orange-500" />
          </div>
          <h2 className="font-display text-lg font-semibold">Garmin Connect</h2>
          {garminStatus?.connected && (
            <span className="ml-auto px-2 py-0.5 text-xs font-medium bg-green-500/10 text-green-400 rounded-full">
              연동됨
            </span>
          )}
        </div>

        {/* Status Messages */}
        {error && (
          <div className="flex items-center gap-2 p-3 mb-4 bg-red-500/10 border border-red-500/20 rounded-lg text-red-400 text-sm">
            <AlertCircle className="w-4 h-4 flex-shrink-0" />
            <span>{error}</span>
          </div>
        )}
        {success && (
          <div className="flex items-center gap-2 p-3 mb-4 bg-green-500/10 border border-green-500/20 rounded-lg text-green-400 text-sm">
            <CheckCircle2 className="w-4 h-4 flex-shrink-0" />
            <span>{success}</span>
          </div>
        )}

        {garminLoading ? (
          <div className="flex items-center justify-center py-8">
            <RefreshCw className="w-6 h-6 animate-spin text-muted" />
          </div>
        ) : garminStatus?.connected ? (
          /* Connected State */
          <div className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-muted mb-1">세션 상태</label>
                <p className="text-[var(--color-text-primary)]">
                  {garminStatus.session_valid ? (
                    <span className="text-green-400">활성</span>
                  ) : (
                    <span className="text-yellow-400">갱신 필요</span>
                  )}
                </p>
              </div>
              <div>
                <label className="block text-sm text-muted mb-1">마지막 동기화</label>
                <p className="text-[var(--color-text-primary)]">{formatDate(garminStatus.last_sync)}</p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3 pt-2">
              <button
                onClick={handleIncrementalSync}
                disabled={!canSync}
                className="flex items-center gap-2 px-4 py-2 bg-cyan/10 text-cyan rounded-lg hover:bg-cyan/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title={!garminStatus?.session_valid ? '세션 갱신이 필요합니다. 다시 연동해주세요.' : undefined}
              >
                {isSyncing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <RefreshCw className="w-4 h-4" />
                )}
                {isSyncing ? '동기화 중...' : '새 데이터 동기화'}
              </button>
              <button
                onClick={handleFullSync}
                disabled={!canSync}
                className="flex items-center gap-2 px-4 py-2 bg-amber-500/10 text-amber-400 rounded-lg hover:bg-amber-500/20 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
                title={!garminStatus?.session_valid ? '세션 갱신이 필요합니다. 다시 연동해주세요.' : '전체 히스토리를 처음부터 다시 동기화합니다'}
              >
                {isSyncing ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Download className="w-4 h-4" />
                )}
                전체 동기화
              </button>
              <button
                onClick={handleDisconnect}
                disabled={disconnectGarmin.isPending}
                className="flex items-center gap-2 px-4 py-2 bg-red-500/10 text-red-400 rounded-lg hover:bg-red-500/20 transition-colors disabled:opacity-50"
              >
                <Link2Off className="w-4 h-4" />
                {disconnectGarmin.isPending ? '해제 중...' : '연동 해제'}
              </button>
            </div>
          </div>
        ) : (
          /* Not Connected State */
          <form onSubmit={handleConnect} className="space-y-4">
            <p className="text-muted text-sm">
              Garmin Connect 계정을 연동하여 러닝 데이터를 자동으로 동기화하세요.
            </p>

            <div>
              <label htmlFor="garmin-email" className="block text-sm font-medium text-muted mb-1.5">
                Garmin 이메일
              </label>
              <input
                id="garmin-email"
                type="email"
                value={garminEmail}
                onChange={(e) => setGarminEmail(e.target.value)}
                placeholder="garmin@example.com"
                className="w-full px-4 py-2.5 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-cyan/50 focus:border-cyan transition-colors"
              />
            </div>

            <div>
              <label htmlFor="garmin-password" className="block text-sm font-medium text-muted mb-1.5">
                Garmin 비밀번호
              </label>
              <input
                id="garmin-password"
                type="password"
                value={garminPassword}
                onChange={(e) => setGarminPassword(e.target.value)}
                placeholder="••••••••"
                className="w-full px-4 py-2.5 bg-[var(--color-bg-tertiary)] border border-[var(--color-border)] rounded-lg text-[var(--color-text-primary)] placeholder-[var(--color-text-muted)] focus:outline-none focus:ring-2 focus:ring-cyan/50 focus:border-cyan transition-colors"
              />
            </div>

            <button
              type="submit"
              disabled={connectGarmin.isPending}
              className="flex items-center gap-2 px-4 py-2.5 bg-cyan text-[var(--color-bg-primary)] font-semibold rounded-lg hover:bg-cyan/90 transition-colors disabled:opacity-50"
            >
              <Link2 className="w-4 h-4" />
              {connectGarmin.isPending ? '연동 중...' : 'Garmin 연동하기'}
            </button>

            <p className="text-xs text-muted">
              * Garmin 세션 정보는 서버에 저장되어 자동 동기화에 사용됩니다.
            </p>
          </form>
        )}
      </div>

      {/* Data Sync Info */}
      {garminStatus?.connected && (
        <div className="card p-6">
          <h3 className="font-display font-semibold mb-3">동기화 정보</h3>

          {/* Sync Type Explanation */}
          <div className="mb-4 p-4 bg-[var(--color-bg-tertiary)] rounded-lg">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <h4 className="font-medium text-cyan mb-1">새 데이터 동기화</h4>
                <p className="text-muted">
                  마지막 동기화 이후의 새로운 데이터만 가져옵니다. 빠르고 효율적입니다.
                </p>
              </div>
              <div>
                <h4 className="font-medium text-amber-400 mb-1">전체 동기화</h4>
                <p className="text-muted">
                  처음부터 모든 히스토리를 다시 가져옵니다. 데이터가 많으면 시간이 오래 걸릴 수 있습니다.
                </p>
              </div>
            </div>
          </div>

          <p className="text-muted text-sm">
            Garmin Connect에서 다음 데이터가 동기화됩니다:
          </p>
          <ul className="mt-3 space-y-2 text-sm">
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              러닝/워킹 활동 기록
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              심박수 데이터
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              수면 데이터
            </li>
            <li className="flex items-center gap-2">
              <CheckCircle2 className="w-4 h-4 text-green-400" />
              스트레스/바디배터리
            </li>
          </ul>
        </div>
      )}
    </div>
  );
}
