import React, { useEffect } from 'react';
import { Outlet, useNavigate } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { useUiStore } from '../../stores/uiStore';
import { useHotkey } from '../../hooks/useHotkey';

export const Layout: React.FC = () => {
  const { sidebarOpen, setSidebarOpen } = useUiStore();
  const navigate = useNavigate();

  // Global shortcut: Cmd/Ctrl+K — jump to Compose Zone (new report).
  useHotkey({ mod: true, key: 'k', allowInEditable: true }, () => {
    navigate('/');
  }, [navigate]);
  // Global shortcut: Cmd/Ctrl+/ — toggle sidebar.
  useHotkey({ mod: true, key: '/' }, () => {
    setSidebarOpen(!sidebarOpen);
  }, [sidebarOpen, setSidebarOpen]);

  useEffect(() => {
    const sync = () => {
      if (window.innerWidth < 1024) setSidebarOpen(false);
    };
    sync();
    window.addEventListener('resize', sync);
    return () => window.removeEventListener('resize', sync);
  }, [setSidebarOpen]);

  return (
    <div className="flex h-screen overflow-hidden bg-canvas">
      <div className="relative z-30 flex-shrink-0">
        <Sidebar open={sidebarOpen} onToggle={() => setSidebarOpen(!sidebarOpen)} />
      </div>

      {sidebarOpen && (
        <button
          aria-label="关闭侧边栏"
          onClick={() => setSidebarOpen(false)}
          className="fixed inset-0 z-20 bg-veil backdrop-blur-[2px] md:hidden"
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
        <Header />
        <main className="flex-1 overflow-hidden">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
