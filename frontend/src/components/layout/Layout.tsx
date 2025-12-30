import { useState } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useUser, useGarminStatus } from '../../hooks/useAuth';

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { data: user, isLoading, error } = useUser();
  const { data: garminStatus } = useGarminStatus();

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-cyan animate-pulse">불러오는 중...</div>
      </div>
    );
  }

  // Redirect to login if not authenticated
  if (error || !user) {
    return <Navigate to="/login" replace />;
  }

  return (
    <div className="min-h-screen">
      <Header
        isConnected={garminStatus?.connected ?? false}
        lastSync={garminStatus?.last_sync ?? null}
        onMenuToggle={() => setSidebarOpen(true)}
        user={user}
      />
      <Sidebar isOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />

      {/* Main content - responsive margin */}
      <main className="pt-16 min-h-[calc(100vh-4rem)] lg:ml-64">
        <div className="p-4 lg:p-6 max-w-[1600px] mx-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
