import { useState } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useUser } from '../../hooks/useAuth';
import { AxiosError } from 'axios';

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { data: user, isLoading, error } = useUser();

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-cyan animate-pulse">불러오는 중...</div>
      </div>
    );
  }

  // Only redirect to login on auth errors (401/403), not network errors
  const isAuthError =
    error instanceof AxiosError &&
    (error.response?.status === 401 || error.response?.status === 403);

  if (isAuthError || !user) {
    return <Navigate to="/login" replace />;
  }

  // Show error state for network/server errors (not auth-related)
  if (error) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center p-6">
          <p className="text-red-400 mb-2">연결 오류가 발생했습니다</p>
          <button
            onClick={() => window.location.reload()}
            className="btn btn-primary text-sm"
          >
            다시 시도
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen">
      <Header
        onMenuToggle={() => setSidebarOpen(true)}
        user={user}
      />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content - responsive margin */}
      <main className="pt-16 min-h-[calc(100vh-4rem)] lg:ml-64">
        <div className="p-4 lg:p-6 xl:p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
