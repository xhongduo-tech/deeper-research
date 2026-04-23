import React, { useEffect, useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowLeft,
  CheckCircle2,
  Clock,
  Database,
  Download,
  Loader2,
  MessageSquare,
  Play,
  Send,
  Sparkles,
  UserCircle2,
  XCircle,
  FileText,
  CheckCheck,
  Undo2,
  StopCircle,
} from 'lucide-react';
import toast from 'react-hot-toast';

import {
  Badge,
  Button,
  ProgressRing,
  SkeletonText,
  Tabs,
  Textarea,
  cn,
} from '../design-system';
import { ErrorBoundary } from '../components/ErrorBoundary';
import {
  answerClarification,
  cancelReport,
  downloadReport,
  getReport,
  interjectReport,
  replyToReport,
  startReport,
} from '../api/reports';
import { getWorkforce } from '../api/workforce';
import { useReportStore } from '../stores/reportStore';
import { useReportStream } from '../hooks/useReportStream';
import type {
  Clarification,
  ReportDetail,
  ReportMessage,
  WorkforceMember,
} from '../types/report';
import {
  REPORT_STATUS_ACTIVE,
  REPORT_STATUS_LABELS,
  REPORT_STATUS_TONE,
} from '../utils/constants';
import { formatDate, formatRelative } from '../utils/formatters';
import { getApiErrorMessage } from '../utils/errors';

// =============================================================================
// Phase dots
// =============================================================================

const PHASES: Array<{ key: string; label: string }> = [
  { key: 'intake', label: '需求确认' },
  { key: 'scoping', label: '阵容定案' },
  { key: 'producing', label: '生产' },
  { key: 'reviewing', label: '质检' },
  { key: 'delivered', label: '交付' },
];

const PhaseTrack: React.FC<{ current: string }> = ({ current }) => {
  const currentIdx = PHASES.findIndex((p) => p.key === current);
  return (
    <div className="flex items-center gap-2">
      {PHASES.map((p, i) => {
        const reached = currentIdx >= 0 && i <= currentIdx;
        const active = i === currentIdx;
        return (
          <React.Fragment key={p.key}>
            <div className="flex items-center gap-1.5">
              <span
                className={cn(
                  'h-[7px] w-[7px] rounded-full transition-colors',
                  reached ? 'bg-brand' : 'bg-line',
                  active && 'ring-2 ring-brand/30',
                )}
              />
              <span
                className={cn(
                  'text-[11px]',
                  reached ? 'text-ink-1 font-medium' : 'text-ink-3',
                )}
              >
                {p.label}
              </span>
            </div>
            {i < PHASES.length - 1 && (
              <span
                className={cn(
                  'h-px w-4',
                  reached && i + 1 <= currentIdx ? 'bg-brand/60' : 'bg-line',
                )}
              />
            )}
          </React.Fragment>
        );
      })}
    </div>
  );
};

// =============================================================================
// Messages
// =============================================================================

const roleStyle = (role: ReportMessage['role']) => {
  switch (role) {
    case 'supervisor_say':
    case 'supervisor_ask':
      return {
        badge: 'Chief',
        accent: 'border-supervisor/40 bg-supervisor/[0.06]',
        icon: <Sparkles size={12} className="text-supervisor" />,
        nameColor: 'text-supervisor',
      };
    case 'user_reply':
      return {
        badge: '你',
        accent: 'border-line bg-surface',
        icon: <UserCircle2 size={12} className="text-ink-3" />,
        nameColor: 'text-ink-1',
      };
    case 'user_interject':
      return {
        badge: '你 · 插话',
        accent: 'border-warning/40 bg-warning/[0.06]',
        icon: <UserCircle2 size={12} className="text-warning" />,
        nameColor: 'text-warning',
      };
    case 'employee_note':
      return {
        badge: '员工',
        accent: 'border-line-subtle bg-sunken/40',
        icon: <MessageSquare size={12} className="text-ink-3" />,
        nameColor: 'text-ink-1',
      };
    case 'team_change':
      return {
        badge: '阵容变更',
        accent: 'border-info/40 bg-info/[0.06]',
        icon: <CheckCheck size={12} className="text-info" />,
        nameColor: 'text-info',
      };
    case 'phase_transition':
      return {
        badge: '阶段切换',
        accent: 'border-line-subtle bg-mist/60',
        icon: <Clock size={12} className="text-ink-3" />,
        nameColor: 'text-ink-2',
      };
    default:
      return {
        badge: role,
        accent: 'border-line-subtle bg-surface',
        icon: <MessageSquare size={12} className="text-ink-3" />,
        nameColor: 'text-ink-1',
      };
  }
};

const MessageCard: React.FC<{ msg: ReportMessage }> = ({ msg }) => {
  const s = roleStyle(msg.role);
  return (
    <motion.div
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.18 }}
      className={cn('rounded-lg border px-3.5 py-2.5', s.accent)}
    >
      <div className="mb-1 flex items-center gap-2">
        {s.icon}
        <span className={cn('text-[11.5px] font-semibold', s.nameColor)}>
          {msg.author_name || s.badge}
        </span>
        <span className="text-caption text-ink-4">
          {formatRelative(msg.created_at)}
        </span>
      </div>
      <p className="whitespace-pre-wrap text-[13px] leading-relaxed text-ink-1">
        {renderContent(msg.content)}
      </p>
    </motion.div>
  );
};

// minimal **bold** renderer — lightweight, no deps
function renderContent(text: string): React.ReactNode {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return parts.map((p, i) =>
    p.startsWith('**') && p.endsWith('**') ? (
      <strong key={i} className="font-semibold text-ink-1">
        {p.slice(2, -2)}
      </strong>
    ) : (
      <span key={i}>{p}</span>
    ),
  );
}

// =============================================================================
// Clarifications panel
// =============================================================================

const ClarificationCard: React.FC<{
  c: Clarification;
  onAnswer: (opts: { answer?: string; use_default?: boolean }) => void;
  submitting: boolean;
}> = ({ c, onAnswer, submitting }) => {
  const [draft, setDraft] = useState('');
  const answered = c.status !== 'pending';

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      className={cn(
        'rounded-lg border p-3',
        answered
          ? 'border-success/30 bg-success/[0.04]'
          : 'border-supervisor/30 bg-supervisor/[0.04]',
      )}
    >
      <div className="flex items-start gap-2">
        <span
          className={cn(
            'mt-0.5 h-1.5 w-1.5 flex-shrink-0 rounded-full',
            answered ? 'bg-success' : 'bg-supervisor animate-pulse',
          )}
        />
        <div className="flex flex-1 flex-wrap items-baseline gap-2">
          <p className="flex-1 text-[12.5px] font-medium text-ink-1">
            {c.question}
          </p>
          {c.priority === 'high' && (
            <span className="rounded bg-danger/10 px-1.5 py-0.5 text-[10px] font-semibold text-danger">
              必填
            </span>
          )}
          {c.priority === 'low' && (
            <span className="rounded bg-sunken px-1.5 py-0.5 text-[10px] text-ink-4">
              可选
            </span>
          )}
        </div>
      </div>

      {answered ? (
        <div className="mt-2 pl-3.5 text-[12px] text-ink-2">
          <span className="text-ink-4">已回复 · </span>
          {c.answer}
          {c.status === 'defaulted' && (
            <span className="ml-1 text-success">(采纳默认)</span>
          )}
        </div>
      ) : (
        <div className="mt-2 space-y-2 pl-3.5">
          {c.default_answer && (
            <div className="rounded-md border border-dashed border-line-subtle bg-surface px-2.5 py-1.5 text-[11.5px] text-ink-3">
              <span className="font-semibold text-ink-2">默认:</span>{' '}
              {c.default_answer}
            </div>
          )}
          <Textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            placeholder="输入你的回答,或点右侧一键采纳默认…"
            autoResize
            minRows={1}
            maxRows={4}
            className="text-[12.5px]"
          />
          <div className="flex items-center justify-end gap-2">
            {c.default_answer && (
              <Button
                variant="ghost"
                size="xs"
                leftIcon={<CheckCheck size={12} />}
                disabled={submitting}
                onClick={() => onAnswer({ use_default: true })}
              >
                采纳默认
              </Button>
            )}
            <Button
              variant="supervisor"
              size="xs"
              leftIcon={<Send size={11} />}
              disabled={submitting || !draft.trim()}
              onClick={() => onAnswer({ answer: draft.trim() })}
            >
              回复
            </Button>
          </div>
        </div>
      )}
    </motion.div>
  );
};

// =============================================================================
// Right pane — full Markdown renderer
// =============================================================================

/** Strip evidence citation IDs like [E10-1-c12ebd9f] from user-visible text. */
function stripEvidenceIds(text: string): string {
  return text.replace(/\[E\d+[-\w]*\]/g, '').replace(/\s{2,}/g, ' ');
}

/** Render inline spans: **bold**, *italic*, `code` */
const renderInline = (s: string, keyPrefix = ''): React.ReactNode => {
  const parts: React.ReactNode[] = [];
  const regex = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*|`[^`\n]+`)/g;
  let last = 0; let key = 0;
  let m: RegExpExecArray | null = null;
  while ((m = regex.exec(s)) !== null) {
    const start = m.index ?? 0;
    if (start > last) parts.push(<span key={`${keyPrefix}t${key++}`}>{s.slice(last, start)}</span>);
    const tok = m[0];
    if (tok.startsWith('**'))
      parts.push(<strong key={`${keyPrefix}b${key++}`} className="font-semibold text-ink-1">{tok.slice(2,-2)}</strong>);
    else if (tok.startsWith('*'))
      parts.push(<em key={`${keyPrefix}i${key++}`} className="italic text-ink-2">{tok.slice(1,-1)}</em>);
    else
      parts.push(<code key={`${keyPrefix}c${key++}`} className="rounded bg-panel-2 px-1.5 py-0.5 font-mono text-[11px] text-ink-2">{tok.slice(1,-1)}</code>);
    last = start + tok.length;
  }
  if (last < s.length) parts.push(<span key={`${keyPrefix}t${key++}`}>{s.slice(last)}</span>);
  return parts;
};

/** Parse a GitHub-flavor markdown table block into headers + rows */
function parseMdTable(lines: string[]): { headers: string[]; rows: string[][] } | null {
  const dataLines = lines.filter((l) => !/^\s*\|[\s\-:|]+\|\s*$/.test(l));
  if (dataLines.length < 1) return null;
  const parse = (l: string) => l.trim().replace(/^\||\|$/g, '').split('|').map((c) => c.trim());
  const [headerLine, ...rowLines] = dataLines;
  return { headers: parse(headerLine), rows: rowLines.map(parse) };
}

const MdTable: React.FC<{ headers: string[]; rows: string[][] }> = ({ headers, rows }) => (
  <div className="my-3 overflow-x-auto rounded-lg border border-line-subtle">
    <table className="min-w-full text-[12px]">
      <thead className="bg-sunken/60">
        <tr>
          {headers.map((h, i) => (
            <th key={i} className="border-b border-line-subtle px-3 py-2 text-left font-semibold text-ink-1 whitespace-nowrap">
              {renderInline(h, `th${i}`)}
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((row, ri) => (
          <tr key={ri} className={ri % 2 === 1 ? 'bg-sunken/20' : ''}>
            {headers.map((_, ci) => (
              <td key={ci} className="border-b border-line-subtle/50 px-3 py-1.5 text-ink-2 align-top">
                {renderInline(row[ci] ?? '', `td${ri}-${ci}`)}
              </td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  </div>
);

/** Full markdown-to-React renderer supporting h2/h3, tables, bullets, numbered, blockquotes, bold */
const renderSectionBody = (rawText: string): React.ReactNode => {
  const text = stripEvidenceIds(rawText);
  const nodes: React.ReactNode[] = [];
  const lines = text.split('\n');
  let i = 0;
  let listBuf: { ordered: boolean; items: string[] } | null = null;

  const flushList = () => {
    if (!listBuf) return;
    const { ordered, items } = listBuf;
    const Tag = ordered ? 'ol' : 'ul';
    nodes.push(
      <Tag key={`list-${i}`} className={ordered ? 'my-2 list-decimal pl-5 space-y-0.5' : 'my-2 list-disc pl-5 space-y-0.5'}>
        {items.map((it, k) => (
          <li key={k} className="text-[13px] leading-relaxed text-ink-2">{renderInline(it, `li${k}`)}</li>
        ))}
      </Tag>,
    );
    listBuf = null;
  };

  while (i < lines.length) {
    const line = lines[i];

    // Markdown table block
    if (/^\s*\|/.test(line)) {
      flushList();
      const block: string[] = [];
      while (i < lines.length && /^\s*\|/.test(lines[i])) { block.push(lines[i]); i++; }
      const parsed = parseMdTable(block);
      if (parsed) nodes.push(<MdTable key={`tbl-${i}`} {...parsed} />);
      continue;
    }

    // ATX headings
    const hm = line.match(/^(#{2,3})\s+(.*)/);
    if (hm) {
      flushList();
      const depth = hm[1].length;
      const cls = depth === 2
        ? 'mt-4 mb-1 text-[14px] font-semibold text-ink-1'
        : 'mt-3 mb-0.5 text-[13px] font-medium text-ink-2';
      nodes.push(<div key={`h${i}`} className={cls}>{renderInline(hm[2], `h${i}`)}</div>);
      i++; continue;
    }

    // Bullet
    const bm = line.match(/^\s*[-*]\s+(.*)/);
    if (bm) {
      if (!listBuf || listBuf.ordered) { flushList(); listBuf = { ordered: false, items: [] }; }
      listBuf.items.push(bm[1]);
      i++; continue;
    }

    // Numbered
    const nm = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (nm) {
      if (!listBuf || !listBuf.ordered) { flushList(); listBuf = { ordered: true, items: [] }; }
      listBuf.items.push(nm[1]);
      i++; continue;
    }

    // Blockquote
    if (line.startsWith('> ')) {
      flushList();
      nodes.push(
        <blockquote key={`bq-${i}`} className="my-1 border-l-2 border-line-subtle pl-3 text-[12.5px] italic text-ink-4">
          {renderInline(line.slice(2), `bq${i}`)}
        </blockquote>,
      );
      i++; continue;
    }

    // Empty line
    if (!line.trim()) { flushList(); i++; continue; }

    // Normal paragraph
    flushList();
    nodes.push(
      <p key={`p-${i}`} className="leading-[1.8] text-ink-2">
        {renderInline(line.trim(), `p${i}`)}
      </p>,
    );
    i++;
  }
  flushList();
  return nodes;
};

// ---------------------------------------------------------------------------
// Data Context panel — shows verified sandbox metrics
// ---------------------------------------------------------------------------
const DataContextBadge: React.FC<{ ctx: Record<string, any> }> = ({ ctx }) => {
  const entries = Object.entries(ctx).slice(0, 12);
  if (!entries.length) return null;
  return (
    <div className="mx-5 mt-3 rounded-lg border border-brand/20 bg-brand-soft/10 p-3">
      <div className="mb-1.5 flex items-center gap-1.5">
        <Database size={11} className="text-brand" />
        <span className="text-[11px] font-semibold uppercase tracking-[0.14em] text-brand">
          已验证数据 · {entries.length} 项
        </span>
      </div>
      <div className="grid grid-cols-2 gap-x-4 gap-y-1">
        {entries.map(([k, v]) => (
          <div key={k} className="flex items-baseline gap-1.5 overflow-hidden">
            <span className="shrink-0 text-[10px] text-ink-4 font-mono">{k}</span>
            <span className="truncate text-[11.5px] font-semibold text-ink-1">
              {String((v as any)?.value ?? v)}
              {(v as any)?.unit ? <span className="ml-0.5 text-[10px] text-ink-3">{(v as any).unit}</span> : null}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
};

const OutputPreview: React.FC<{ report: ReportDetail }> = ({ report }) => {
  const [downloading, setDownloading] = useState(false);
  const [activeTab, setActiveTab] = useState<'content' | 'trace'>('content');
  const outline = report.section_outline ?? [];
  const outputs = (report.output_index ?? {}) as Record<
    string,
    { text: string; employee_name?: string; note?: string; error?: string | null }
  >;
  const dataCtx = report.data_context as Record<string, any> | null | undefined;
  const traceLog = report.trace_log as Record<string, any> | null | undefined;
  const delivered = report.status === 'delivered';
  const producing = ['scoping', 'producing', 'reviewing'].includes(report.status);
  const producedCount = outline.filter((s) => outputs[s.id]?.text).length;

  // Header content varies by state.
  const header = (
    <div className="flex items-center justify-between border-b border-line-subtle px-5 py-3">
      <div className="flex items-center gap-2">
        {delivered ? (
          <>
            <CheckCircle2 size={14} className="text-success" />
            <span className="text-[13px] font-semibold text-ink-1">最终交付</span>
            {traceLog && (
              <div className="flex rounded-md border border-line bg-sunken/40 p-0.5 ml-3">
                {(['content', 'trace'] as const).map((tab) => (
                  <button
                    key={tab}
                    type="button"
                    onClick={() => setActiveTab(tab)}
                    className={[
                      'rounded px-2 py-0.5 text-[11px] font-medium transition-colors',
                      activeTab === tab
                        ? 'bg-surface text-ink-1 shadow-sm'
                        : 'text-ink-3 hover:text-ink-2',
                    ].join(' ')}
                  >
                    {tab === 'content' ? '报告' : '执行追踪'}
                  </button>
                ))}
              </div>
            )}
          </>
        ) : (
          <>
            <FileText size={14} className="text-ink-3" />
            <span className="text-[13px] font-semibold text-ink-1">输出预览</span>
            {producing && (
              <Badge size="xs" tone="info" variant="soft">
                生产中 · {producedCount}/{outline.length || '?'}
              </Badge>
            )}
          </>
        )}
      </div>
      {delivered && report.final_file_name ? (
        <Button
          size="xs"
          variant="secondary"
          leftIcon={<Download size={12} />}
          loading={downloading}
          onClick={async () => {
            setDownloading(true);
            try {
              await downloadReport(report.id, report.final_file_name || undefined);
            } catch (err) {
              console.error('download failed', err);
            } finally {
              setDownloading(false);
            }
          }}
        >
          下载 Word
        </Button>
      ) : (
        <ProgressRing
          value={report.progress}
          size={36}
          thickness={3}
          active={producing}
        />
      )}
    </div>
  );

  // Body: prefer real sections; fall back to skeleton when nothing is written
  // yet (early scoping phase).
  return (
    <div className="flex h-full flex-col">
      {header}
      {/* Trace log tab */}
      {activeTab === 'trace' && traceLog && (
        <div className="flex-1 overflow-y-auto px-5 py-4 text-[12px]">
          <p className="mb-3 font-semibold text-ink-1">执行追踪日志</p>
          {/* Summary */}
          <div className="mb-4 grid grid-cols-3 gap-3">
            {[
              ['执行步骤', (traceLog.execution_plan as any[] | undefined)?.length ?? 0],
              ['验证数据', Object.keys(traceLog.data_context ?? {}).length],
              ['耗时', `${traceLog.elapsed_s ?? '?'}s`],
            ].map(([label, val]) => (
              <div key={label} className="rounded-lg border border-line bg-sunken/30 p-2 text-center">
                <p className="text-[18px] font-bold text-ink-1">{val}</p>
                <p className="text-[10px] text-ink-3">{label}</p>
              </div>
            ))}
          </div>
          {/* Trace entries */}
          <div className="space-y-2">
            {((traceLog.trace ?? []) as any[]).map((entry: any, i: number) => (
              <div key={i} className="rounded border border-line bg-surface p-2.5">
                <div className="flex items-center gap-2">
                  <span className={[
                    'rounded px-1.5 py-0.5 text-[10px] font-mono font-semibold',
                    entry.action === 'code_exec' ? 'bg-amber-100 text-amber-700' :
                    entry.action === 'qa_check' ? 'bg-purple-100 text-purple-700' :
                    entry.action === 'security_scan' ? 'bg-red-100 text-red-600' :
                    'bg-blue-50 text-blue-600',
                  ].join(' ')}>{entry.action}</span>
                  <span className="text-[11px] text-ink-3">{entry.agent_id}</span>
                  <span className="ml-auto text-[10px] text-ink-4">
                    +{Math.round((entry.ts - ((traceLog.trace as any[])?.[0]?.ts ?? entry.ts)))}s
                  </span>
                </div>
                <p className="mt-1 text-ink-2">{entry.output_summary}</p>
                {entry.code && (
                  <details className="mt-1">
                    <summary className="cursor-pointer text-[10px] text-brand">查看代码</summary>
                    <pre className="mt-1 overflow-x-auto rounded bg-[#1e1e1e] p-2 text-[10.5px] text-green-300">{entry.code}</pre>
                  </details>
                )}
                {entry.error && (
                  <p className="mt-1 text-[10.5px] text-danger">{entry.error}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
      {activeTab === 'content' && (
      <div className="flex-1 overflow-y-auto px-8 py-6">
        {dataCtx && Object.keys(dataCtx).length > 0 && (
          <DataContextBadge ctx={dataCtx} />
        )}
        <div className="mx-auto max-w-[720px]">
          <h1 className="font-serif text-[22px] font-semibold text-ink-1">
            {report.title}
          </h1>
          {delivered && (
            <p className="mt-2 text-[12px] text-ink-3">
              {formatDate(report.completed_at || report.updated_at)}
            </p>
          )}

          {outline.length === 0 ? (
            <div className="mt-6">
              <SkeletonText lines={8} />
            </div>
          ) : (
            <div className="mt-8 space-y-7">
              {outline.map((s) => {
                const out = outputs[s.id];
                return (
                  <section key={s.id}>
                    <div className="flex items-baseline justify-between gap-3">
                      <h2 className="text-[15px] font-semibold text-ink-1">
                        {s.title}
                      </h2>
                      {out?.employee_name && (
                        <span className="text-[11px] text-ink-4">
                          by {out.employee_name}
                        </span>
                      )}
                    </div>
                    {out?.text ? (
                      <div className="mt-2 space-y-3 text-[13px] leading-[1.75] text-ink-2">
                        {renderSectionBody(out.text)}
                      </div>
                    ) : (
                      <div className="mt-2">
                        <SkeletonText lines={3} />
                      </div>
                    )}
                  </section>
                );
              })}
            </div>
          )}
        </div>
      </div>
      )}
    </div>
  );
};

// =============================================================================
// Team strip — clickable member badges with popover detail
// =============================================================================

const MemberPopover: React.FC<{
  member: WorkforceMember;
  isSupervisor?: boolean;
  onClose: () => void;
}> = ({ member, isSupervisor, onClose }) => (
  <div
    className="absolute bottom-full left-0 z-50 mb-2 w-64 rounded-xl border border-line-subtle bg-elevated p-4 shadow-pop"
    onClick={(e) => e.stopPropagation()}
  >
    <div className="mb-2 flex items-start justify-between gap-2">
      <div>
        <p className={cn('text-[13px] font-semibold', isSupervisor ? 'text-supervisor' : 'text-ink-1')}>
          {member.first_name_en}
        </p>
        <p className="text-[11px] text-ink-3">{member.role_title_en}</p>
      </div>
      <button
        onClick={onClose}
        className="mt-0.5 flex h-5 w-5 items-center justify-center rounded text-ink-4 hover:text-ink-2"
      >
        ×
      </button>
    </div>
    {member.description && (
      <p className="mb-2 text-[12px] leading-relaxed text-ink-2">{member.description}</p>
    )}
    {member.skills && member.skills.length > 0 && (
      <div className="flex flex-wrap gap-1">
        {member.skills.slice(0, 8).map((s) => (
          <span key={s} className="rounded bg-sunken px-1.5 py-0.5 text-[10.5px] text-ink-3">{s}</span>
        ))}
      </div>
    )}
  </div>
);

const TeamBadge: React.FC<{
  member: WorkforceMember;
  isSupervisor?: boolean;
}> = ({ member, isSupervisor }) => {
  const [open, setOpen] = useState(false);
  const ref = React.useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={cn(
          'flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors',
          isSupervisor
            ? 'border-supervisor/35 bg-supervisor/[0.08] text-supervisor hover:bg-supervisor/[0.15]'
            : 'border-line-subtle bg-sunken/50 text-ink-2 hover:border-line hover:bg-sunken',
        )}
        title="点击查看角色说明"
      >
        {member.first_name_en}
      </button>
      {open && (
        <MemberPopover member={member} isSupervisor={isSupervisor} onClose={() => setOpen(false)} />
      )}
    </div>
  );
};

const TeamStrip: React.FC<{
  team: string[];
  workforce?: WorkforceMember[];
  supervisor?: WorkforceMember;
}> = ({ team, workforce = [], supervisor }) => {
  const map = useMemo(() => {
    const m = new Map<string, WorkforceMember>();
    workforce.forEach((w) => m.set(w.id, w));
    if (supervisor) m.set(supervisor.id, supervisor);
    return m;
  }, [workforce, supervisor]);

  const members = team
    .map((id) => map.get(id))
    .filter((m): m is WorkforceMember => Boolean(m));

  if (!supervisor && members.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {supervisor && <TeamBadge member={supervisor} isSupervisor />}
      {members.map((m) => <TeamBadge key={m.id} member={m} />)}
    </div>
  );
};

// =============================================================================
// Main page
// =============================================================================

const ReportPageInner: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const reportId = Number(id);
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    currentReport,
    setCurrentReport,
    appendMessage,
    applyStatusPatch,
    applySectionOutput,
    upsertClarification,
    appendTimeline,
  } = useReportStore();

  // Fetch initial
  const reportQ = useQuery({
    queryKey: ['report', reportId],
    queryFn: () => getReport(reportId),
    enabled: Number.isFinite(reportId) && reportId > 0,
    staleTime: 2000,
  });

  const workforceQ = useQuery({
    queryKey: ['workforce'],
    queryFn: getWorkforce,
    staleTime: 10 * 60 * 1000,
  });

  useEffect(() => {
    if (reportQ.data) setCurrentReport(reportQ.data);
    return () => setCurrentReport(null);
  }, [reportQ.data, setCurrentReport]);

  // Live stream
  useReportStream(Number.isFinite(reportId) ? reportId : null, (evt) => {
    if (evt.type === 'message') appendMessage(evt.payload);
    else if (evt.type === 'clarification') upsertClarification(evt.payload);
    else if (evt.type === 'timeline') appendTimeline(evt.payload);
    else if (evt.type === 'status') {
      applyStatusPatch(evt.payload as Partial<import('../types/report').Report>);
      // When delivered, refetch once to get final_file_name/path from DB
      if (evt.payload?.status === 'delivered') {
        setTimeout(() => {
          queryClient.invalidateQueries({ queryKey: ['report', reportId] });
        }, 800);
      }
    } else if (evt.type === 'section_output' && evt.payload?.section_id)
      applySectionOutput(evt.payload.section_id, evt.payload.output ?? {});
  });

  // Auto-scroll feed to bottom on new messages
  const feedRef = useRef<HTMLDivElement | null>(null);
  useEffect(() => {
    if (!feedRef.current) return;
    feedRef.current.scrollTop = feedRef.current.scrollHeight;
  }, [currentReport?.messages?.length]);

  // -------- Mutations --------
  const replyMut = useMutation({
    mutationFn: (content: string) => replyToReport(reportId, content),
    onError: (err: any) =>
      toast.error(getApiErrorMessage(err, '发送失败')),
  });
  const interjectMut = useMutation({
    mutationFn: (content: string) => interjectReport(reportId, content),
    onError: (err: any) =>
      toast.error(getApiErrorMessage(err, '发送失败')),
  });
  const answerMut = useMutation({
    mutationFn: ({
      cid,
      opts,
    }: {
      cid: number;
      opts: { answer?: string; use_default?: boolean };
    }) => answerClarification(reportId, cid, opts),
    onSuccess: (updated) => upsertClarification(updated),
    onError: (err: any) =>
      toast.error(getApiErrorMessage(err, '回复失败')),
  });
  const startMut = useMutation({
    mutationFn: () => startReport(reportId),
    onSuccess: () => toast.success('已通知 Chief 开工'),
    onError: (err: any) =>
      toast.error(getApiErrorMessage(err, '启动失败')),
  });
  const cancelMut = useMutation({
    mutationFn: () => cancelReport(reportId),
    onSuccess: () => {
      toast.success('已取消');
      queryClient.invalidateQueries({ queryKey: ['report', reportId] });
    },
  });

  // -------- Input composer --------
  const [composerMode, setComposerMode] = useState<'reply' | 'interject'>('reply');
  const [composerText, setComposerText] = useState('');
  const sendComposer = () => {
    const text = composerText.trim();
    if (!text) return;
    if (composerMode === 'interject') {
      interjectMut.mutate(text);
    } else {
      replyMut.mutate(text);
    }
    setComposerText('');
  };

  // -------- Render --------
  if (!reportQ.isLoading && !currentReport) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-2 text-center">
          <XCircle size={28} className="text-ink-4" />
          <p className="text-[13px] text-ink-3">报告不存在或已被删除</p>
          <Button variant="outline" size="sm" onClick={() => navigate('/')}>
            返回主页
          </Button>
        </div>
      </div>
    );
  }

  if (!currentReport) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 size={22} className="animate-spin text-ink-3" />
      </div>
    );
  }

  const report = currentReport;
  const messages = report.messages ?? [];
  const clarifications = report.clarifications ?? [];
  const pendingClarifications = clarifications.filter(
    (c) => c.status === 'pending',
  );
  const running = REPORT_STATUS_ACTIVE.has(report.status);
  const canStart = ['draft', 'intake'].includes(report.status);

  return (
    <div className="flex h-full flex-col">
      {/* Top bar */}
      <div className="flex flex-shrink-0 items-center justify-between border-b border-line-subtle bg-surface/80 px-5 py-3 backdrop-blur">
        <div className="flex min-w-0 items-center gap-3">
          <button
            onClick={() => navigate('/')}
            aria-label="返回"
            className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-md text-ink-3 hover:bg-sunken hover:text-ink-1"
          >
            <ArrowLeft size={15} />
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-[14.5px] font-semibold text-ink-1">
                {report.title}
              </h1>
              <Badge
                size="xs"
                tone={REPORT_STATUS_TONE[report.status] || 'neutral'}
                variant="soft"
                dot
                pulsing={running}
              >
                {REPORT_STATUS_LABELS[report.status] || report.status}
              </Badge>
            </div>
            <div className="mt-1 flex items-center gap-3">
              <PhaseTrack current={report.phase} />
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {canStart && (
            <Button
              size="sm"
              variant="supervisor"
              leftIcon={<Play size={12} />}
              loading={startMut.isPending}
              onClick={() => startMut.mutate()}
            >
              开始生产
            </Button>
          )}
          {running && (
            <Button
              size="sm"
              variant="outline"
              leftIcon={<StopCircle size={12} />}
              loading={cancelMut.isPending}
              onClick={() => cancelMut.mutate()}
            >
              取消
            </Button>
          )}
        </div>
      </div>

      {/* Team strip */}
      {report.team_roster && report.team_roster.length > 0 && (
        <div className="flex flex-shrink-0 items-center gap-3 border-b border-line-subtle bg-sunken/30 px-5 py-2">
          <span className="text-caption uppercase tracking-[0.18em] text-ink-3">
            阵容
          </span>
          <TeamStrip
            team={report.team_roster}
            workforce={workforceQ.data?.employees}
            supervisor={workforceQ.data?.supervisor}
          />
        </div>
      )}

      {/* Split layout */}
      <div className="flex min-h-0 flex-1">
        {/* Left: Collaboration Room */}
        <section className="flex w-[46%] min-w-[380px] flex-shrink-0 flex-col border-r border-line-subtle bg-canvas">
          <div className="flex items-center justify-between border-b border-line-subtle px-5 py-2.5">
            <div className="flex items-center gap-1.5">
              <MessageSquare size={13} className="text-ink-3" />
              <span className="text-[12.5px] font-semibold text-ink-1">
                协作室
              </span>
            </div>
            <span className="text-caption text-ink-4">
              {messages.length} 条消息
            </span>
          </div>

          {/* Clarifications (pinned on top) */}
          {pendingClarifications.length > 0 && (
            <div className="flex-shrink-0 space-y-2 border-b border-line-subtle bg-supervisor/[0.03] px-4 py-3">
              <p className="flex items-center gap-1.5 text-caption uppercase tracking-[0.18em] text-supervisor">
                <Sparkles size={10} />
                Chief 请你确认({pendingClarifications.length})
              </p>
              <AnimatePresence initial={false}>
                {pendingClarifications.map((c) => (
                  <ClarificationCard
                    key={c.id}
                    c={c}
                    submitting={answerMut.isPending}
                    onAnswer={(opts) =>
                      answerMut.mutate({ cid: c.id, opts })
                    }
                  />
                ))}
              </AnimatePresence>
            </div>
          )}

          {/* Feed */}
          <div
            ref={feedRef}
            className="custom-scrollbar flex-1 space-y-2 overflow-y-auto px-4 py-3"
          >
            <AnimatePresence initial={false}>
              {messages.map((m) => (
                <MessageCard key={m.id} msg={m} />
              ))}
            </AnimatePresence>
            {messages.length === 0 && (
              <div className="flex h-full items-center justify-center text-[12px] text-ink-4">
                等待 Chief 开场…
              </div>
            )}
          </div>

          {/* Composer */}
          <div className="flex-shrink-0 border-t border-line-subtle bg-surface px-4 py-3">
            <div className="mb-1.5 flex items-center gap-1.5 text-[11px]">
              <button
                onClick={() => setComposerMode('reply')}
                className={cn(
                  'rounded px-2 py-0.5 transition-colors',
                  composerMode === 'reply'
                    ? 'bg-brand-soft text-brand'
                    : 'text-ink-3 hover:bg-sunken',
                )}
              >
                回复
              </button>
              <button
                onClick={() => setComposerMode('interject')}
                className={cn(
                  'rounded px-2 py-0.5 transition-colors',
                  composerMode === 'interject'
                    ? 'bg-warning/15 text-warning'
                    : 'text-ink-3 hover:bg-sunken',
                )}
              >
                插话指示
              </button>
            </div>
            <Textarea
              value={composerText}
              onChange={(e) => setComposerText(e.target.value)}
              placeholder={
                composerMode === 'interject'
                  ? '给进行中的生产加一条即时指示(会在下一轮产出中体现)…'
                  : '回复 Chief 或提供补充信息…'
              }
              autoResize
              minRows={2}
              maxRows={6}
              className="text-[13px]"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  sendComposer();
                }
              }}
            />
            <div className="mt-1.5 flex items-center justify-between">
              <span className="text-caption text-ink-4">⌘/Ctrl + Enter 发送</span>
              <Button
                size="xs"
                variant={composerMode === 'interject' ? 'outline' : 'primary'}
                leftIcon={
                  composerMode === 'interject' ? (
                    <Undo2 size={11} />
                  ) : (
                    <Send size={11} />
                  )
                }
                disabled={
                  !composerText.trim() ||
                  replyMut.isPending ||
                  interjectMut.isPending
                }
                onClick={sendComposer}
              >
                {composerMode === 'interject' ? '插话' : '发送'}
              </Button>
            </div>
          </div>
        </section>

        {/* Right: Output Preview */}
        <section className="flex min-w-0 flex-1 flex-col bg-surface">
          <OutputPreview report={report} />
        </section>
      </div>
    </div>
  );
};

export const ReportPage: React.FC = () => (
  <ErrorBoundary label="报告协作室">
    <ReportPageInner />
  </ErrorBoundary>
);

export default ReportPage;
