import { useState } from 'react';
import { Outlet, Navigate, useLocation } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';
import { useAuthContext, CLERK_ENABLED } from '../../contexts/AuthContext';

export function Layout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const { user, isLoading, isAuthenticated, clerkEnabled } = useAuthContext();
  const location = useLocation();

  console.log('[Layout] Auth state:', { user: !!user, isLoading, isAuthenticated, clerkEnabled });

  // Show loading state
  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-accent animate-pulse">불러오는 중...</div>
      </div>
    );
  }

  // Not authenticated - redirect to appropriate login page
  if (!isAuthenticated) {
    console.log('[Layout] Not authenticated, redirecting');
    // In Clerk mode, redirect to Clerk sign-in
    if (CLERK_ENABLED) {
      return <Navigate to="/sign-in" state={{ from: location }} replace />;
    }
    // In session mode, redirect to login
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return (
    <div className="min-h-screen">
      <Header
        onMenuToggle={() => setSidebarOpen(true)}
        user={user ?? undefined}
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
