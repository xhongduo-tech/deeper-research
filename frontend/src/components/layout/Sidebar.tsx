import React from 'react';
import { motion } from 'framer-motion';
import {
  Plus,
  ChevronsLeft,
  ChevronsRight,
  LogIn,
  LogOut,
  Home,
  Archive,
  Users,
  Code2,
  Settings,
  Clock,
} from 'lucide-react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import toast from 'react-hot-toast';

import { useAuthStore } from '../../stores/authStore';
import { useUiStore } from '../../stores/uiStore';
import { listReports } from '../../api/reports';
import { logout as apiLogout } from '../../api/auth';
import { BrandMark } from '../ui';
import { Badge, cn } from '../../design-system';
import {
  REPORT_STATUS_LABELS,
  REPORT_STATUS_TONE,
  REPORT_STATUS_ACTIVE,
} from '../../utils/constants';
import { formatDate, truncateText } from '../../utils/formatters';
import type { Report } from '../../types/report';

// ----------------------------- Nav button -----------------------------

const NavButton: React.FC<{
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  collapsed?: boolean;
}> = ({ active, onClick, icon, label, collapsed }) => (
  <button
    onClick={onClick}
    title={collapsed ? label : undefined}
    className={cn(
      'relative flex w-full items-center gap-3 rounded-md px-3 py-2 text-[13.5px] font-medium transition-all',
      active
        ? 'bg-ink-1/[0.06] text-ink-1'
        : 'text-ink-2 hover:bg-ink-1/[0.04] hover:text-ink-1',
      collapsed && 'justify-center',
    )}
  >
    {active && (
      <span className="absolute inset-y-1.5 left-0 w-[3px] rounded-r-full bg-brand" />
    )}
    <span className="flex-shrink-0">{icon}</span>
    {!collapsed && <span className="truncate">{label}</span>}
  </button>
);

// ----------------------------- Report history item --------------------

const ReportHistoryItem: React.FC<{
  report: Report;
  active: boolean;
  onClick: () => void;
}> = ({ report, active, onClick }) => (
  <button
    onClick={onClick}
    className={cn(
      'group w-full rounded-md px-2.5 py-2 text-left transition-all',
      active ? 'bg-brand-soft/70 ring-1 ring-brand/25' : 'hover:bg-sunken/60',
    )}
  >
    <div className="flex items-start justify-between gap-2">
      <span
        className={cn(
          'flex-1 truncate text-[13px] font-medium leading-tight',
          active ? 'text-ink-1' : 'text-ink-2 group-hover:text-ink-1',
        )}
      >
        {truncateText(report.title, 28)}
      </span>
      <span className="text-caption flex-shrink-0 text-ink-4">
        {formatDate(report.updated_at)}
      </span>
    </div>
    <div className="mt-1.5">
      <Badge
        tone={REPORT_STATUS_TONE[report.status] || 'neutral'}
        variant="soft"
        size="xs"
        dot
        pulsing={REPORT_STATUS_ACTIVE.has(report.status)}
      >
        {REPORT_STATUS_LABELS[report.status] || report.status}
      </Badge>
    </div>
  </button>
);

// ============================= Component =============================

interface SidebarProps {
  open: boolean;
  onToggle: () => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ open, onToggle }) => {
  const navigate = useNavigate();
  const location = useLocation();
  const {
    user,
    isAuthenticated,
    openLoginModal,
    logout: storeLogout,
  } = useAuthStore();

  // Recent reports for the sidebar history list
  const reportsQ = useQuery({
    queryKey: ['reports', 'sidebar'],
    queryFn: () => listReports({ limit: 30 }),
    enabled: isAuthenticated,
    staleTime: 5 * 1000,
    refetchOnWindowFocus: true,
  });

  const handleLogout = async () => {
    try {
      await apiLogout();
    } catch {}
    storeLogout();
    toast.success('已退出登录');
  };

  const currentReportId = React.useMemo(() => {
    const m = location.pathname.match(/^\/reports\/(\d+)/);
    return m ? Number(m[1]) : null;
  }, [location.pathname]);

  const isActive = (path: string) =>
    path === '/' ? location.pathname === '/' : location.pathname.startsWith(path);

  return (
    <motion.aside
      animate={{ width: open ? 272 : 68 }}
      transition={{ duration: 0.25, ease: [0.2, 0, 0, 1] }}
      className="relative flex h-full flex-col overflow-hidden border-r border-line-subtle bg-surface/80 backdrop-blur-[2px]"
    >
      {/* Brand */}
      <div
        className={cn(
          'flex flex-shrink-0 items-center border-b border-line-subtle',
          open ? 'gap-3 px-5 py-5' : 'justify-center px-0 py-5',
        )}
      >
        <BrandMark size={open ? 36 : 32} />
        {open && (
          <div className="min-w-0">
            <h1 className="truncate font-serif text-[15px] font-semibold text-ink-1">
              深度研究数据分析智能体
            </h1>
            <p className="mt-0.5 text-[10.5px] uppercase tracking-[0.22em] text-ink-3">
              dataagent
            </p>
          </div>
        )}
      </div>

      {/* Primary nav */}
      <div className={cn('flex flex-col gap-1', open ? 'px-3 pt-4' : 'px-2 pt-4')}>
        <NavButton
          active={isActive('/')}
          onClick={() => navigate('/')}
          icon={<Home size={17} />}
          label="新建报告"
          collapsed={!open}
        />
        <NavButton
          active={isActive('/archive')}
          onClick={() => navigate('/archive')}
          icon={<Archive size={17} />}
          label="档案库"
          collapsed={!open}
        />
        <NavButton
          active={isActive('/workforce')}
          onClick={() => navigate('/workforce')}
          icon={<Users size={17} />}
          label="数字员工"
          collapsed={!open}
        />
        <NavButton
          active={isActive('/developer')}
          onClick={() => navigate('/developer')}
          icon={<Code2 size={17} />}
          label="开发者"
          collapsed={!open}
        />
      </div>

      {/* New report CTA */}
      <div className={cn('mt-3 flex-shrink-0', open ? 'px-3' : 'px-2')}>
        <button
          onClick={() => navigate('/')}
          title={!open ? '新建报告' : undefined}
          className={cn(
            'ds-btn ds-btn-primary h-10 w-full shadow-xs',
            open ? '' : 'px-0',
          )}
        >
          <Plus size={16} />
          {open && <span>新建报告</span>}
        </button>
      </div>

      {/* Recent reports */}
      <div className="mt-5 flex min-h-0 flex-1 flex-col">
        {open && (
          <div className="flex items-center justify-between px-5 pb-2">
            <div className="text-caption flex items-center gap-1.5 font-semibold uppercase tracking-[0.14em] text-ink-3">
              <Clock size={12} />
              最近的报告
            </div>
            {isAuthenticated && reportsQ.data?.items.length ? (
              <span className="text-caption text-ink-4">
                {reportsQ.data.items.length}
              </span>
            ) : null}
          </div>
        )}

        <div className="custom-scrollbar flex-1 overflow-y-auto px-2 pb-3">
          {!open ? null : !isAuthenticated ? (
            <div className="mx-1 rounded-md border border-dashed border-line-subtle px-3 py-4 text-center">
              <p className="text-[12.5px] leading-relaxed text-ink-3">
                登录后可以看到你创建的报告
              </p>
            </div>
          ) : reportsQ.isLoading ? (
            <div className="space-y-1.5 px-1">
              {[0, 1, 2].map((i) => (
                <div
                  key={i}
                  className="h-[48px] animate-pulse rounded-md bg-sunken/60"
                />
              ))}
            </div>
          ) : (reportsQ.data?.items.length ?? 0) === 0 ? (
            <div className="px-3 py-6 text-center text-[12.5px] text-ink-3">
              暂无报告
            </div>
          ) : (
            <div className="space-y-0.5">
              {reportsQ.data!.items.map((r) => (
                <ReportHistoryItem
                  key={r.id}
                  report={r}
                  active={currentReportId === r.id}
                  onClick={() => navigate(`/reports/${r.id}`)}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <div
        className={cn(
          'flex-shrink-0 border-t border-line-subtle',
          open ? 'px-3 py-3' : 'px-2 py-3',
        )}
      >
        <NavButton
          active={isActive('/admin')}
          onClick={() => {
            if (user?.role === 'admin') navigate('/admin');
            else openLoginModal(() => navigate('/admin'));
          }}
          icon={<Settings size={17} />}
          label="管理后台"
          collapsed={!open}
        />

        {isAuthenticated ? (
          <div
            className={cn(
              'mt-2 flex items-center gap-2.5 rounded-md',
              open ? 'px-2 py-2' : 'justify-center px-0 py-2',
            )}
          >
            <div
              className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full bg-cedar-soft text-[12px] font-semibold text-cedar"
              aria-hidden
            >
              {user?.username?.[0]?.toUpperCase() || 'U'}
            </div>
            {open && (
              <>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[12.5px] font-medium text-ink-1">
                    {user?.username}
                  </p>
                  <p className="text-caption text-ink-3">
                    {user?.role === 'admin' ? '管理员' : '普通用户'}
                  </p>
                </div>
                <button
                  onClick={handleLogout}
                  aria-label="退出登录"
                  className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-ink-3 transition-colors hover:bg-danger-soft hover:text-danger"
                >
                  <LogOut size={14} />
                </button>
              </>
            )}
          </div>
        ) : open ? (
          <button
            onClick={() => openLoginModal()}
            className="mt-2 flex w-full items-center justify-center gap-2 rounded-md border border-line px-3 py-2 text-[12.5px] font-medium text-ink-2 transition-colors hover:border-line-strong hover:bg-sunken/60"
          >
            <LogIn size={13} />
            登录 / 注册
          </button>
        ) : (
          <button
            onClick={() => openLoginModal()}
            aria-label="登录"
            className="mt-2 flex h-9 w-full items-center justify-center rounded-md border border-line text-ink-3 hover:text-ink-1"
          >
            <LogIn size={14} />
          </button>
        )}

        {/* Toggle */}
        <button
          onClick={onToggle}
          aria-label={open ? '收起侧边栏' : '展开侧边栏'}
          className="mt-2 flex h-8 w-full items-center justify-center rounded-md text-ink-3 transition-colors hover:bg-sunken/60 hover:text-ink-1"
        >
          {open ? <ChevronsLeft size={15} /> : <ChevronsRight size={15} />}
        </button>
      </div>
    </motion.aside>
  );
};

export default Sidebar;
