import React, { Suspense, useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { useAuthStore } from './stores/authStore';
import { setAuthToken } from './api/client';
import { Layout } from './components/layout/Layout';
import { LoginPage } from './pages/LoginPage';
import { HomePage } from './pages/HomePage';
import { ReportPage } from './pages/ReportPage';
import { ArchivePage } from './pages/ArchivePage';
import { WorkforcePage } from './pages/WorkforcePage';
import { DeveloperPage } from './pages/DeveloperPage';
import { AdminPage } from './pages/AdminPage';
import { LoginModal } from './components/auth/LoginModal';
import { PageLoader } from './components/common/LoadingSpinner';
import './styles/globals.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 30 * 1000,
      refetchOnWindowFocus: false,
    },
    mutations: { retry: 0 },
  },
});

const AdminRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated, user } = useAuthStore();
  if (!isAuthenticated) return <LoginPage />;
  if (user?.role !== 'admin') return <Navigate to="/" replace />;
  return <>{children}</>;
};

const PublicRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuthStore();
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <>{children}</>;
};

// Restores the axios header token after a page refresh.
const AppBootstrap: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { token } = useAuthStore();
  useEffect(() => {
    if (token) setAuthToken(token);
  }, [token]);
  return <>{children}</>;
};

const GlobalLoginModal: React.FC = () => {
  const { loginModalOpen, loginSuccessCallback, closeLoginModal } = useAuthStore();
  return (
    <LoginModal
      open={loginModalOpen}
      onClose={closeLoginModal}
      onSuccess={() => loginSuccessCallback?.()}
    />
  );
};

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicRoute>
            <LoginPage />
          </PublicRoute>
        }
      />

      <Route path="/" element={<Layout />}>
        <Route index element={<HomePage />} />
        <Route path="reports/:id" element={<ReportPage />} />
        <Route path="archive" element={<ArchivePage />} />
        <Route path="workforce" element={<WorkforcePage />} />
        <Route path="developer" element={<DeveloperPage />} />
        <Route
          path="admin"
          element={
            <AdminRoute>
              <AdminPage />
            </AdminRoute>
          }
        />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppBootstrap>
          <Suspense fallback={<PageLoader />}>
            <AppRoutes />
          </Suspense>
          <GlobalLoginModal />
          <Toaster
            position="top-right"
            toastOptions={{
              duration: 3200,
              style: {
                background: '#ffffff',
                color: '#1a1a1a',
                border: '1px solid #e5e5e5',
                borderRadius: '10px',
                padding: '10px 14px',
                fontSize: '13px',
                fontFamily:
                  'Inter, -apple-system, BlinkMacSystemFont, "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei", sans-serif',
                boxShadow:
                  '0 12px 32px -10px rgba(0,0,0,0.18), 0 4px 10px -4px rgba(0,0,0,0.08)',
              },
              success: {
                iconTheme: { primary: '#2a7a4e', secondary: '#ffffff' },
              },
              error: {
                iconTheme: { primary: '#b83a3a', secondary: '#ffffff' },
              },
            }}
          />
        </AppBootstrap>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
