import React, { useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import { Archive, Search, FileText, ArrowRight } from 'lucide-react';
import { listReports } from '../api/reports';
import { listReportTypes } from '../api/reportTypes';
import {
  Input,
  Badge,
  Skeleton,
  Select,
  EmptyState,
  ErrorState,
} from '../design-system';
import {
  REPORT_STATUS_LABELS,
  REPORT_STATUS_TONE,
  REPORT_STATUS_ACTIVE,
} from '../utils/constants';
import { formatDate } from '../utils/formatters';
import type { Report, ReportType } from '../types/report';

export const ArchivePage: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState<ReportType | 'all'>('all');

  const reportsQ = useQuery({
    queryKey: ['reports', 'all'],
    queryFn: () => listReports({ limit: 200 }),
    staleTime: 10 * 1000,
  });
  const typesQ = useQuery({
    queryKey: ['report-types'],
    queryFn: listReportTypes,
    staleTime: 60 * 60 * 1000,
  });

  const typeLabel = useMemo(() => {
    const map = new Map<string, string>();
    typesQ.data?.items.forEach((t) => map.set(t.id, t.label));
    return map;
  }, [typesQ.data]);

  const filtered = useMemo(() => {
    const all = reportsQ.data?.items ?? [];
    return all.filter((r) => {
      if (typeFilter !== 'all' && r.report_type !== typeFilter) return false;
      const s = search.trim().toLowerCase();
      if (!s) return true;
      return `${r.title} ${r.brief}`.toLowerCase().includes(s);
    });
  }, [reportsQ.data, search, typeFilter]);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-[1100px] px-6 py-10">
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 flex flex-col gap-2"
        >
          <span className="flex items-center gap-1.5 text-caption uppercase tracking-[0.2em] text-ink-3">
            <Archive size={11} />
            档案库
          </span>
          <h1 className="font-serif text-[24px] font-semibold text-ink-1">
            历史报告
          </h1>
          <p className="max-w-[620px] text-[13px] leading-relaxed text-ink-2">
            你创建过的所有报告都在这里。支持按标题搜索与类型筛选。
          </p>
        </motion.div>

        <div className="mb-4 flex flex-wrap items-center gap-3">
          <div className="w-[320px] flex-shrink-0">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="搜索标题或描述…"
              leftIcon={<Search size={13} />}
            />
          </div>
          <div className="w-[200px]">
            <Select
              value={typeFilter}
              onChange={(v) => setTypeFilter(v as any)}
              options={[
                { value: 'all', label: '全部类型' },
                ...(typesQ.data?.items.map((t) => ({
                  value: t.id,
                  label: t.label,
                })) ?? []),
              ]}
            />
          </div>
          <span className="ml-auto text-caption text-ink-3">
            共 {filtered.length} 份
          </span>
        </div>

        {reportsQ.isLoading ? (
          <div className="flex flex-col gap-2">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-[64px] rounded-lg" />
            ))}
          </div>
        ) : reportsQ.isError ? (
          <div className="rounded-lg border border-dashed border-line-subtle">
            <ErrorState
              description="无法获取报告列表,请检查网络或重试。"
              onRetry={() => reportsQ.refetch()}
              retrying={reportsQ.isFetching}
            />
          </div>
        ) : filtered.length === 0 ? (
          <div className="rounded-lg border border-dashed border-line-subtle">
            <EmptyState
              icon={<FileText size={20} />}
              title="暂无匹配的报告"
              description="调整搜索条件,或回到首页创建一份新的报告。"
            />
          </div>
        ) : (
          <div className="overflow-hidden rounded-lg border border-line-subtle bg-surface">
            {filtered.map((r: Report, i) => {
              const tone = REPORT_STATUS_TONE[r.status] || 'neutral';
              const active = REPORT_STATUS_ACTIVE.has(r.status);
              return (
                <button
                  key={r.id}
                  onClick={() => navigate(`/reports/${r.id}`)}
                  className={[
                    'group flex w-full items-center gap-3 px-4 py-3.5 text-left transition-colors hover:bg-sunken/60',
                    i > 0 ? 'border-t border-line-subtle' : '',
                  ].join(' ')}
                >
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-[13.5px] font-semibold text-ink-1">
                        {r.title}
                      </span>
                      <Badge
                        size="xs"
                        tone={tone}
                        variant="soft"
                        dot
                        pulsing={active}
                      >
                        {REPORT_STATUS_LABELS[r.status] || r.status}
                      </Badge>
                    </div>
                    <div className="mt-1 flex items-center gap-3 text-[11.5px] text-ink-3">
                      <span>
                        {typeLabel.get(r.report_type) || r.report_type}
                      </span>
                      <span className="text-ink-4">·</span>
                      <span>{formatDate(r.updated_at)}</span>
                      <span className="text-ink-4">·</span>
                      <span>{Math.round((r.progress || 0) * 100)}%</span>
                    </div>
                  </div>
                  <ArrowRight
                    size={15}
                    className="flex-shrink-0 text-ink-4 transition-transform group-hover:translate-x-0.5 group-hover:text-ink-2"
                  />
                </button>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};

export default ArchivePage;
