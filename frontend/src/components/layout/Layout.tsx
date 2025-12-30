import { useState } from 'react';
import { Outlet, Navigate } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useUser } from '../../hooks/useAuth';

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

  // Redirect to login if not authenticated
  if (error || !user) {
    return <Navigate to="/login" replace />;
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
