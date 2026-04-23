import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Trash2, RefreshCw, ChevronLeft, ChevronRight, Inbox } from 'lucide-react';
import { getAllReports, adminDeleteReport } from '../../api/admin';
import { ConfirmDialog } from '../common/ConfirmDialog';
import { formatDateTime, truncateText } from '../../utils/formatters';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Badge } from '../../design-system';
import {
  REPORT_STATUS_LABELS,
  REPORT_STATUS_TONE,
  REPORT_STATUS_ACTIVE,
} from '../../utils/constants';
import toast from 'react-hot-toast';

export const TaskMonitor: React.FC = () => {
  const [page, setPage] = useState(1);
  const [deleteTarget, setDeleteTarget] = useState<number | null>(null);
  const [deleting, setDeleting] = useState(false);
  const queryClient = useQueryClient();
  const pageSize = 15;

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-reports', page],
    queryFn: () => getAllReports(page, pageSize),
    refetchInterval: 10000,
  });

  const reports = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / pageSize);

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setDeleting(true);
    try {
      await adminDeleteReport(deleteTarget);
      toast.success('报告已删除');
      setDeleteTarget(null);
      queryClient.invalidateQueries({ queryKey: ['admin-reports'] });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || '删除失败');
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Toolbar */}
      <div className="flex items-center justify-between">
        <span className="text-[13px] text-ink-2">
          共 <strong className="text-ink-1 tabular-nums">{total}</strong> 份报告
        </span>
        <Button
          variant="outline"
          size="sm"
          onClick={() => refetch()}
          leftIcon={
            <RefreshCw
              size={13}
              className={isLoading ? 'animate-spin' : ''}
            />
          }
        >
          刷新
        </Button>
      </div>

      {/* Table */}
      <div className="ds-card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="border-b border-line bg-surface">
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  ID
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  标题
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  用户
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  状态
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  创建时间
                </th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center text-[13px] text-ink-3">
                    <div className="flex items-center justify-center gap-2">
                      <RefreshCw size={14} className="animate-spin" />
                      加载中…
                    </div>
                  </td>
                </tr>
              ) : reports.length === 0 ? (
                <tr>
                  <td colSpan={6} className="py-12 text-center">
                    <div className="flex flex-col items-center gap-2 text-ink-3">
                      <Inbox size={22} className="text-ink-4" />
                      <span className="text-[13px]">暂无报告记录</span>
                    </div>
                  </td>
                </tr>
              ) : (
                reports.map((report, i) => (
                  <motion.tr
                    key={report.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className="border-b border-line-subtle transition-colors hover:bg-surface/60"
                  >
                    <td className="px-4 py-3 font-mono text-[12px] text-ink-3">
                      #{report.id}
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[13.5px] text-ink-1">
                        {truncateText(report.title, 40)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[12.5px] text-ink-2">
                        用户 {report.user_id}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <Badge
                        size="xs"
                        tone={REPORT_STATUS_TONE[report.status] || 'neutral'}
                        variant="soft"
                        dot
                        pulsing={REPORT_STATUS_ACTIVE.has(report.status)}
                      >
                        {REPORT_STATUS_LABELS[report.status] || report.status}
                      </Badge>
                    </td>
                    <td className="px-4 py-3">
                      <span className="text-[12px] text-ink-3 tabular-nums">
                        {formatDateTime(report.created_at)}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          onClick={() => setDeleteTarget(report.id)}
                          className="rounded-md p-1.5 text-ink-3 transition-colors hover:bg-danger-soft hover:text-danger"
                          title="删除报告"
                          aria-label="删除报告"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </td>
                  </motion.tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-center gap-3">
          <button
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            disabled={page === 1}
            className="ds-btn ds-btn-outline h-8 w-8 !p-0 disabled:opacity-40"
            aria-label="上一页"
          >
            <ChevronLeft size={14} />
          </button>
          <span className="text-[13px] text-ink-2 tabular-nums">
            第 {page} 页 / 共 {totalPages} 页
          </span>
          <button
            onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
            disabled={page === totalPages}
            className="ds-btn ds-btn-outline h-8 w-8 !p-0 disabled:opacity-40"
            aria-label="下一页"
          >
            <ChevronRight size={14} />
          </button>
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        onClose={() => setDeleteTarget(null)}
        onConfirm={handleDelete}
        title="删除报告"
        message={`确认删除报告 #${deleteTarget}？此操作不可撤销,相关文件和结果将一并删除。`}
        confirmText="确认删除"
        variant="danger"
        loading={deleting}
      />
    </div>
  );
};

export default TaskMonitor;
