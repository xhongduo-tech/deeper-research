import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Users, Settings, Activity, ArrowLeft } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { getAgentConfigs, getSystemConfig, getSystemStats } from '../api/admin';
import { getWorkforce } from '../api/workforce';
import { toLegacyEmployee } from '../utils/workforceAdapter';
import { EmployeeConfig } from '../components/admin/EmployeeConfig';
import { SystemSettings } from '../components/admin/SystemSettings';
import { TaskMonitor } from '../components/admin/TaskMonitor';
import { PageLoader } from '../components/common/LoadingSpinner';
import type { SystemConfig } from '../types';

type AdminTab = 'employees' | 'settings' | 'monitor';

const TABS = [
  { id: 'employees' as AdminTab, label: '员工配置', icon: Users },
  { id: 'settings' as AdminTab, label: '系统设置', icon: Settings },
  { id: 'monitor' as AdminTab, label: '报告监控', icon: Activity },
];

export const AdminPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<AdminTab>('employees');
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const { data: employees = [], isLoading: loadingEmployees } = useQuery({
    queryKey: ['admin-workforce'],
    queryFn: async () => {
      const wf = await getWorkforce();
      return wf.employees.map(toLegacyEmployee);
    },
    staleTime: 5 * 60 * 1000,
  });

  const {
    data: agentConfigs = [],
    isLoading: loadingConfigs,
    refetch: refetchConfigs,
  } = useQuery({
    queryKey: ['agent-configs'],
    queryFn: getAgentConfigs,
  });

  const {
    data: systemConfig,
    isLoading: loadingSystemConfig,
    refetch: refetchSystemConfig,
  } = useQuery({
    queryKey: ['system-config'],
    queryFn: getSystemConfig,
  });

  const { data: stats } = useQuery({
    queryKey: ['admin-stats'],
    queryFn: getSystemStats,
    refetchInterval: 30000,
  });

  const [localSystemConfig, setLocalSystemConfig] = useState<SystemConfig | null>(null);
  const displaySystemConfig = localSystemConfig || systemConfig;

  const isLoading = loadingEmployees || loadingConfigs || loadingSystemConfig;

  if (isLoading) return <PageLoader text="加载管理后台..." />;

  const statPills = stats
    ? [
        { label: '报告总数', value: stats.total_reports, tone: 'neutral' as const },
        { label: '进行中', value: stats.running_reports, tone: 'cedar' as const },
        { label: '已交付', value: stats.completed_reports, tone: 'success' as const },
        { label: '失败', value: stats.failed_reports, tone: 'danger' as const },
      ]
    : [];

  const pillTone: Record<
    'neutral' | 'cedar' | 'success' | 'danger',
    { bg: string; text: string }
  > = {
    neutral: { bg: 'bg-sunken', text: 'text-ink-1' },
    cedar: { bg: 'bg-cedar-soft', text: 'text-cedar' },
    success: { bg: 'bg-success-soft', text: 'text-success' },
    danger: { bg: 'bg-danger-soft', text: 'text-danger' },
  };

  return (
    <div className="flex h-full flex-col overflow-hidden bg-paper">
      {/* Admin header */}
      <div className="flex-shrink-0 border-b border-line-subtle bg-elevated/70 px-6 py-4 backdrop-blur-[2px]">
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/')}
              className="inline-flex items-center gap-1.5 text-small text-ink-3 transition-colors hover:text-ink-1"
            >
              <ArrowLeft size={14} />
              返回工作台
            </button>
            <div className="h-4 w-px bg-line" />
            <div>
              <span className="ds-eyebrow">管理员后台</span>
              <h1 className="text-h4 font-semibold text-ink-1">系统配置与监控</h1>
            </div>
          </div>

          {/* Stats pills */}
          {statPills.length > 0 && (
            <div className="hidden items-center gap-2.5 md:flex">
              {statPills.map((stat) => (
                <div
                  key={stat.label}
                  className={`flex items-center gap-2 rounded-md px-3 py-1.5 ${pillTone[stat.tone].bg}`}
                >
                  <span className={`text-body font-semibold ${pillTone[stat.tone].text}`}>
                    {stat.value}
                  </span>
                  <span className="text-caption uppercase tracking-wider text-ink-3">
                    {stat.label}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Tab navigation */}
      <div className="flex-shrink-0 border-b border-line-subtle bg-elevated/50 px-6">
        <div className="flex items-center gap-1">
          {TABS.map((tab) => {
            const Icon = tab.icon;
            const isActive = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={[
                  'relative flex items-center gap-2 px-4 py-3 text-small font-medium transition-colors',
                  isActive
                    ? 'text-brand'
                    : 'text-ink-3 hover:text-ink-1',
                ].join(' ')}
              >
                <Icon size={14} />
                {tab.label}
                {isActive && (
                  <motion.span
                    layoutId="admin-tab-indicator"
                    className="absolute inset-x-2 -bottom-px h-0.5 rounded-full bg-brand"
                  />
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto p-6 custom-scrollbar">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.2 }}
        >
          {activeTab === 'employees' && (
            <EmployeeConfig
              employees={employees}
              agentConfigs={agentConfigs}
              systemConfig={displaySystemConfig}
              onConfigUpdated={() => {
                refetchConfigs();
                queryClient.invalidateQueries({ queryKey: ['agent-configs'] });
              }}
            />
          )}

          {activeTab === 'settings' && displaySystemConfig && (
            <SystemSettings
              config={displaySystemConfig}
              onConfigUpdated={(updated) => {
                setLocalSystemConfig(updated);
                refetchSystemConfig();
              }}
            />
          )}

          {activeTab === 'monitor' && <TaskMonitor />}
        </motion.div>
      </div>
    </div>
  );
};

export default AdminPage;
