import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Layout } from './components/layout/Layout';
import { Login } from './pages/Login';
import { Dashboard } from './pages/Dashboard';
import { Activities } from './pages/Activities';
import { ActivityDetail } from './pages/ActivityDetail';
import { Trends } from './pages/Trends';
import { Records } from './pages/Records';
import { Calendar } from './pages/Calendar';
import { Gear } from './pages/Gear';
import { Strength } from './pages/Strength';
import { Coach } from './pages/Coach';
import { Settings } from './pages/Settings';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
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

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />

          {/* Protected routes */}
          <Route element={<Layout />}>
            <Route path="/" element={<Dashboard />} />
            <Route path="/activities" element={<Activities />} />
            <Route path="/activities/:id" element={<ActivityDetail />} />
            <Route path="/trends" element={<Trends />} />
            <Route path="/records" element={<Records />} />
            <Route path="/calendar" element={<Calendar />} />
            <Route path="/gear" element={<Gear />} />
            <Route path="/strength" element={<Strength />} />
            <Route path="/workouts" element={<PlaceholderPage title="Workouts" />} />
            <Route path="/ai" element={<Coach />} />
            <Route path="/settings" element={<Settings />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
