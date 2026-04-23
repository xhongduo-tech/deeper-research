import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Sparkles, Search, LogIn, Users } from 'lucide-react';
import axios from 'axios';
import { getWorkforce } from '../api/workforce';
import { EmployeeCard } from '../components/agents/EmployeeCard';
import { ErrorBoundary } from '../components/ErrorBoundary';
import {
  Input,
  Skeleton,
  EmptyState,
  ErrorState,
} from '../design-system';
import { toLegacyEmployee } from '../utils/workforceAdapter';
import type { WorkforceMember } from '../types/report';
import { useAuthStore } from '../stores/authStore';

const WorkforcePageInner: React.FC = () => {
  const { isAuthenticated, openLoginModal } = useAuthStore();
  const q = useQuery({
    queryKey: ['workforce'],
    queryFn: getWorkforce,
    staleTime: 10 * 60 * 1000,
    // Only fire once we actually have a session; otherwise the request
    // 401s and the page looks "broken" to the user.
    enabled: isAuthenticated,
    retry: (failureCount, err) => {
      if (axios.isAxiosError(err) && err.response && err.response.status < 500) {
        return false;
      }
      return failureCount < 2;
    },
  });
  const [search, setSearch] = useState('');

  const errStatus =
    q.error && axios.isAxiosError(q.error)
      ? q.error.response?.status
      : undefined;
  const errDetail =
    q.error && axios.isAxiosError(q.error)
      ? (q.error.response?.data as { detail?: string } | undefined)?.detail ??
        q.error.message
      : q.error instanceof Error
        ? q.error.message
        : undefined;

  const filtered = useMemo(() => {
    const list = q.data?.employees ?? [];
    const s = search.trim().toLowerCase();
    if (!s) return list;
    return list.filter((m: WorkforceMember) =>
      [
        m.first_name_en,
        m.role_title_en,
        m.tagline_en,
        m.name,
        m.description,
        ...(m.skills ?? []),
      ]
        .join(' ')
        .toLowerCase()
        .includes(s),
    );
  }, [q.data, search]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1400px] px-6 py-10">
        {/* Hero */}
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex flex-col gap-2"
        >
          <span className="flex items-center gap-1.5 text-caption uppercase tracking-[0.2em] text-ink-3">
            <Sparkles size={11} className="text-brand" />
            数字员工
          </span>
          <h1 className="font-serif text-[24px] font-semibold text-ink-1">
            这些人在你的报告团队里。
          </h1>
          <p className="max-w-[640px] text-[13px] leading-relaxed text-ink-2">
            用户不直接调度他们 — Chief 会按报告类型自动组阵。
            这里仅供你了解每位员工的职责边界。
          </p>
        </motion.div>

        {/* Search */}
        <div className="mb-5 max-w-[360px]">
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索 Elin、Remy、合规、风险…"
            leftIcon={<Search size={13} />}
          />
        </div>

        {/* Chief hero card */}
        {q.data?.supervisor && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-7 grid grid-cols-1 gap-4 lg:grid-cols-[320px_1fr]"
          >
            <div>
              <EmployeeCard
                employee={toLegacyEmployee(q.data.supervisor)}
                showLanyard
              />
            </div>
            <div className="flex flex-col justify-center gap-2 rounded-lg border border-line-subtle bg-sunken/40 p-5">
              <span className="text-caption uppercase tracking-[0.18em] text-supervisor">
                Production Supervisor
              </span>
              <h2 className="text-[17px] font-semibold text-ink-1">
                {q.data.supervisor.first_name_en} ·{' '}
                {q.data.supervisor.role_title_en}
              </h2>
              <p className="text-[13px] leading-relaxed text-ink-2">
                {q.data.supervisor.description}
              </p>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {(q.data.supervisor.skills ?? []).map((s) => (
                  <span
                    key={s}
                    className="rounded-full border border-supervisor/30 bg-supervisor/10 px-2 py-0.5 text-[11px] text-supervisor"
                  >
                    {s}
                  </span>
                ))}
              </div>
            </div>
          </motion.div>
        )}

        {/* Employees grid */}
        {!isAuthenticated ? (
          <EmptyState
            icon={<LogIn size={20} />}
            title="请先登录"
            description="登录后即可查看完整的数字员工名册。"
            action={
              <button
                type="button"
                onClick={() => openLoginModal()}
                className="inline-flex items-center gap-1.5 rounded-md bg-brand px-3.5 py-1.5 text-[12.5px] font-medium text-ink-inverse hover:opacity-90"
              >
                <LogIn size={13} />
                立即登录
              </button>
            }
          />
        ) : q.isLoading || q.isFetching && !q.data ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {Array.from({ length: 10 }).map((_, i) => (
              <Skeleton
                key={i}
                className="aspect-[3/4] w-full rounded-[22px]"
              />
            ))}
          </div>
        ) : q.isError ? (
          <ErrorState
            title={
              errStatus === 401
                ? '登录已过期'
                : errStatus
                  ? `加载失败 (HTTP ${errStatus})`
                  : '无法连接到后端'
            }
            description={
              errStatus === 401
                ? '你的会话已失效，请重新登录后再试。'
                : errDetail
                  ? `${errDetail}`
                  : '请检查网络与后端服务是否正常，然后点击「重试」。'
            }
            onRetry={
              errStatus === 401
                ? () => openLoginModal(() => q.refetch())
                : () => q.refetch()
            }
            retrying={q.isFetching}
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={<Users size={20} />}
            title="没有找到匹配的员工"
            description="换个关键词试试,或清空搜索看看完整名册。"
          />
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
            {filtered.map((m) => (
              <EmployeeCard key={m.id} employee={toLegacyEmployee(m)} />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export const WorkforcePage: React.FC = () => (
  <ErrorBoundary label="数字员工">
    <WorkforcePageInner />
  </ErrorBoundary>
);

export default WorkforcePage;
