/**
 * Clerk-enabled App wrapper
 *
 * This file is lazy-loaded only when CLERK_ENABLED is true,
 * so Clerk dependencies are not bundled when not needed.
 */

import { useEffect } from 'react';
import { BrowserRouter, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ClerkProvider, SignIn, SignUp, useAuth } from '@clerk/clerk-react';
import { AuthProvider } from './contexts/AuthContext';
import { ToastProvider } from './contexts/ToastContext';
import { CoreRoutes } from './App';
import { setTokenGetter } from './api/client';

const CLERK_PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY || '';

/**
 * Component to set up token getter for API client
 */
function TokenSetup() {
  const { getToken } = useAuth();

  useEffect(() => {
    setTokenGetter(getToken);
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
 * Clerk routes to inject into CoreRoutes
 */
const clerkRoutes = (
  <>
    <Route path="/sign-in/*" element={<ClerkSignInPage />} />
    <Route path="/sign-up/*" element={<ClerkSignUpPage />} />
  </>
);

interface ClerkAppProps {
  queryClient: QueryClient;
}

/**
 * Full Clerk-enabled App
 */
export default function ClerkApp({ queryClient }: ClerkAppProps) {
  console.log('[ClerkApp] Rendering with Clerk provider');

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
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ToastProvider>
            <TokenSetup />
            <BrowserRouter>
              <CoreRoutes clerkRoutes={clerkRoutes} />
            </BrowserRouter>
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </ClerkProvider>
  );
}
