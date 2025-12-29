import { Outlet } from 'react-router-dom';
import { Header } from './Header';
import { Sidebar } from './Sidebar';

export function Layout() {
  return (
    <div className="min-h-screen">
      <Header isConnected={true} lastSync={new Date().toISOString()} />
      <Sidebar />
      <main className="ml-64 pt-16 min-h-[calc(100vh-4rem)]">
        <div className="p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
