import { Suspense, lazy } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout/Layout';
import { Login } from './pages/Login';

// Lazy-loaded page components for code splitting
const Dashboard = lazy(() => import('./pages/Dashboard').then(m => ({ default: m.Dashboard })));
const Activities = lazy(() => import('./pages/Activities').then(m => ({ default: m.Activities })));
const ActivityDetail = lazy(() => import('./pages/ActivityDetail').then(m => ({ default: m.ActivityDetail })));
const Trends = lazy(() => import('./pages/Trends').then(m => ({ default: m.Trends })));
const Records = lazy(() => import('./pages/Records').then(m => ({ default: m.Records })));
const Calendar = lazy(() => import('./pages/Calendar').then(m => ({ default: m.Calendar })));
const Gear = lazy(() => import('./pages/Gear').then(m => ({ default: m.Gear })));
const GearDetail = lazy(() => import('./pages/GearDetail').then(m => ({ default: m.GearDetail })));
const Strength = lazy(() => import('./pages/Strength').then(m => ({ default: m.Strength })));
const Coach = lazy(() => import('./pages/Coach').then(m => ({ default: m.Coach })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));

// Loading fallback for lazy-loaded components
const PageLoader = () => (
  <div className="flex items-center justify-center min-h-[50vh]">
    <div className="text-cyan animate-pulse">Loading...</div>
  </div>
);

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        // Don't retry on auth errors (401/403)
        if (error && typeof error === 'object' && 'response' in error) {
          const status = (error as { response?: { status?: number } }).response?.status;
          if (status === 401 || status === 403) return false;
        }
        return failureCount < 1;
      },
      refetchOnWindowFocus: false,
    },
  },
});

// Placeholder pages
const PlaceholderPage = ({ title }: { title: string }) => (
  <div className="card">
    <h1 className="font-display text-2xl font-bold mb-4">{title}</h1>
    <p className="text-muted">This page is under construction.</p>
  </div>
);

// 404 Not Found page (for protected routes)
const NotFound = () => (
  <div className="card text-center py-12">
    <h1 className="font-display text-4xl font-bold mb-4">404</h1>
    <p className="text-muted mb-6">Page not found</p>
    <Link to="/" className="btn btn-primary">Go to Dashboard</Link>
  </div>
);

// Public 404 Not Found page (for unauthenticated users)
const PublicNotFound = () => (
  <div className="min-h-screen flex items-center justify-center bg-dark">
    <div className="text-center">
      <h1 className="font-display text-4xl font-bold mb-4 text-cyan">404</h1>
      <p className="text-muted mb-6">Page not found</p>
      <Link to="/login" className="btn btn-primary">Go to Login</Link>
    </div>
  </div>
);

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={<PageLoader />}>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />

            {/* Protected routes - Layout handles auth guard */}
            <Route element={<Layout />}>
              <Route path="/" element={<Dashboard />} />
              <Route path="/activities" element={<Activities />} />
              <Route path="/activities/:id" element={<ActivityDetail />} />
              <Route path="/trends" element={<Trends />} />
              <Route path="/records" element={<Records />} />
              <Route path="/calendar" element={<Calendar />} />
              <Route path="/gear" element={<Gear />} />
              <Route path="/gear/:id" element={<GearDetail />} />
              <Route path="/strength" element={<Strength />} />
              <Route path="/workouts" element={<PlaceholderPage title="Workouts" />} />
              <Route path="/ai" element={<Coach />} />
              <Route path="/settings" element={<Settings />} />
              {/* Protected 404 catch-all (user is authenticated) */}
              <Route path="*" element={<NotFound />} />
            </Route>

            {/* Public 404 catch-all (outside Layout, for /login/* typos etc.) */}
            <Route path="*" element={<PublicNotFound />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
