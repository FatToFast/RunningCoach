import { Suspense, lazy, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Link } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ClerkProvider, SignIn, SignUp, useAuth } from '@clerk/clerk-react';
import { Layout } from './components/layout/Layout';
import { Login } from './pages/Login';
import { AuthProvider } from './contexts/AuthContext';
import { setTokenGetter } from './api/client';

// Environment configuration
const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || '';
const AUTH_MODE = import.meta.env.VITE_AUTH_MODE || 'session';
const CLERK_ENABLED = !!CLERK_PUBLISHABLE_KEY && (AUTH_MODE === 'clerk' || AUTH_MODE === 'hybrid');

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
const Workouts = lazy(() => import('./pages/Workouts').then(m => ({ default: m.Workouts })));

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

/**
 * Component to set up token getter for API client
 */
function TokenSetup() {
  const { getToken } = useAuth();

  useEffect(() => {
    if (CLERK_ENABLED) {
      setTokenGetter(getToken);
    }
  }, [getToken]);

  return null;
}

/**
 * Clerk Sign-In page wrapper
 */
const ClerkSignInPage = () => (
  <div className="min-h-screen bg-[var(--color-bg-primary)] flex items-center justify-center p-4">
    <div className="w-full max-w-md">
      <div className="text-center mb-8">
        <h1 className="font-display text-2xl font-bold">RunningCoach</h1>
        <p className="text-muted text-sm mt-2">러닝 데이터 분석 & AI 코칭</p>
      </div>
      <SignIn
        appearance={{
          elements: {
            rootBox: 'w-full',
            card: 'bg-[var(--color-bg-secondary)] border border-[var(--color-border)]',
          },
        }}
        routing="path"
        path="/sign-in"
        signUpUrl="/sign-up"
        fallbackRedirectUrl="/"
        forceRedirectUrl="/"
      />
    </div>
  </div>
);

/**
 * Clerk Sign-Up page wrapper
 */
const ClerkSignUpPage = () => (
  <div className="min-h-screen bg-[var(--color-bg-primary)] flex items-center justify-center p-4">
    <div className="w-full max-w-md">
      <div className="text-center mb-8">
        <h1 className="font-display text-2xl font-bold">RunningCoach</h1>
        <p className="text-muted text-sm mt-2">러닝 데이터 분석 & AI 코칭</p>
      </div>
      <SignUp
        appearance={{
          elements: {
            rootBox: 'w-full',
            card: 'bg-[var(--color-bg-secondary)] border border-[var(--color-border)]',
          },
        }}
        routing="path"
        path="/sign-up"
        signInUrl="/sign-in"
        fallbackRedirectUrl="/"
        forceRedirectUrl="/"
      />
    </div>
  </div>
);

/**
 * Main App Routes
 */
function AppRoutes() {
  return (
    <Suspense fallback={<PageLoader />}>
      <Routes>
        {/* Public routes */}
        <Route path="/login" element={<Login />} />

        {/* Clerk auth routes (only if Clerk enabled) */}
        {CLERK_ENABLED && (
          <>
            <Route path="/sign-in/*" element={<ClerkSignInPage />} />
            <Route path="/sign-up/*" element={<ClerkSignUpPage />} />
          </>
        )}

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
          <Route path="/workouts" element={<Workouts />} />
          <Route path="/ai" element={<Coach />} />
          <Route path="/settings" element={<Settings />} />
          {/* Protected 404 catch-all (user is authenticated) */}
          <Route path="*" element={<NotFound />} />
        </Route>

        {/* Public 404 catch-all (outside Layout, for /login/* typos etc.) */}
        <Route path="*" element={<PublicNotFound />} />
      </Routes>
    </Suspense>
  );
}

/**
 * App with providers
 */
function AppWithProviders() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        {CLERK_ENABLED && <TokenSetup />}
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  );
}

/**
 * Main App component
 */
function App() {
  // If Clerk is enabled, wrap with ClerkProvider
  if (CLERK_ENABLED) {
    return (
      <ClerkProvider
        publishableKey={CLERK_PUBLISHABLE_KEY}
        appearance={{
          variables: {
            colorPrimary: '#00D4FF',
            colorBackground: '#1a1a2e',
            colorText: '#ffffff',
            colorInputBackground: '#2a2a4e',
            colorInputText: '#ffffff',
          },
        }}
      >
        <AppWithProviders />
      </ClerkProvider>
    );
  }

  // Session-only mode - no Clerk wrapper needed
  return <AppWithProviders />;
}

export default App;
