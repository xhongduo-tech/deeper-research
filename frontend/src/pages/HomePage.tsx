import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  Sparkles,
  FileText,
  Clock,
  CheckCircle2,
  AlertCircle,
  Paperclip,
  X,
  Play,
  Plus,
  Wand2,
  Trash2,
  Eye,
  Users2,
  Check,
  LayoutTemplate,
  Upload,
  ChevronDown,
} from 'lucide-react';
import toast from 'react-hot-toast';

import {
  Button,
  Badge,
  Textarea,
  Skeleton,
  EmptyState,
  Dialog,
  Input,
} from '../design-system';
import { useAuthStore } from '../stores/authStore';
import { useReportStore } from '../stores/reportStore';
import {
  createReport,
  listReports,
} from '../api/reports';
import {
  confirmCustomReportType,
  createCustomReportType,
  deleteCustomReportType,
  listReportTypes,
  reimproveCustomReportType,
  type CustomReportType as CustomRT,
} from '../api/reportTypes';
import { getWorkforce } from '../api/workforce';
import { uploadFile, listTemplates, uploadTemplate, deleteTemplate, type TemplateFile } from '../api/files';
import type {
  Report,
  ReportDetail,
  ReportType,
  ReportTypeInfo,
  WorkforceMember,
} from '../types/report';
import type { UploadedFile } from '../types';
import {
  REPORT_STATUS_LABELS,
  REPORT_STATUS_TONE,
  REPORT_STATUS_ACTIVE,
  FILE_SIZE_LIMIT,
  ACCEPTED_FILE_TYPES,
} from '../utils/constants';
import { formatDate, formatFileSize } from '../utils/formatters';
import { getApiErrorMessage } from '../utils/errors';

// ----------------------------- Chief mini card ---------------------------

const ChiefAvatar: React.FC<{ supervisor?: WorkforceMember }> = ({ supervisor }) => (
  <div className="flex items-center gap-3">
    <div
      className="flex h-12 w-12 flex-shrink-0 items-center justify-center rounded-xl bg-[#141414] font-mono text-[15px] font-semibold text-[#e4c584]"
      style={{
        boxShadow:
          'inset 0 0 0 1px rgba(192,138,58,0.45), 0 1px 0 rgba(255,255,255,0.06) inset',
      }}
    >
      CH
    </div>
    <div>
      <p className="text-[13px] font-semibold text-ink-1">
        {supervisor?.first_name_en || 'Chief'}
        <span className="ml-1.5 text-[11px] font-normal text-ink-3">
          {supervisor?.role_title_en || 'Production Supervisor'}
        </span>
      </p>
      <p className="mt-0.5 text-[11.5px] text-ink-3">
        {supervisor?.tagline_en || 'Run the project, not the task'}
      </p>
    </div>
  </div>
);

// ----------------------------- Report Type chip --------------------------

const TypeChip: React.FC<{
  info: ReportTypeInfo;
  active: boolean;
  onClick: () => void;
}> = ({ info, active, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    className={[
      'group flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-all',
      active
        ? 'border-brand/70 bg-brand-soft/40 ring-1 ring-brand/30'
        : 'border-line bg-surface hover:border-line-strong hover:bg-sunken/40',
    ].join(' ')}
  >
    <div className="flex w-full items-center justify-between">
      <span
        className={[
          'flex items-center gap-1.5 text-[13px] font-semibold',
          active ? 'text-brand' : 'text-ink-1',
        ].join(' ')}
      >
        {info.label}
        {info.is_custom && (
          <span className="rounded-full border border-brand/30 bg-brand-soft px-1.5 py-px text-[9.5px] font-medium uppercase tracking-wider text-brand">
            自定义
          </span>
        )}
      </span>
      <span className="text-caption text-ink-4">{info.label_en}</span>
    </div>
    <p className="line-clamp-2 text-[11.5px] leading-relaxed text-ink-3">
      {info.description}
    </p>
  </button>
);

// ----------------------------- Template picker ---------------------------

const TemplatePickerPanel: React.FC<{
  templates: TemplateFile[];
  selected: number | null;
  onSelect: (id: number | null) => void;
  onUpload: (file: File) => void;
  uploading?: boolean;
}> = ({ templates, selected, onSelect, onUpload, uploading }) => {
  const builtins = templates.filter((t) => t.user_id === 0);
  const custom   = templates.filter((t) => t.user_id !== 0);

  const handleFilePick = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.docx,.pptx';
    input.onchange = (e) => {
      const f = (e.target as HTMLInputElement).files?.[0];
      if (f) onUpload(f);
    };
    input.click();
  };

  const Card: React.FC<{ t: TemplateFile | null }> = ({ t }) => {
    const isActive = t ? selected === t.id : selected === null;
    const label = t ? t.original_name : '默认样式';
    const sub   = t ? t.file_type.toUpperCase() : '系统生成';
    return (
      <button
        type="button"
        onClick={() => onSelect(t ? t.id : null)}
        className={[
          'flex flex-col items-start gap-1 rounded-lg border p-2.5 text-left transition-all',
          isActive
            ? 'border-brand/60 bg-brand-soft/30 ring-1 ring-brand/30'
            : 'border-line bg-surface hover:border-line-strong hover:bg-sunken/40',
        ].join(' ')}
      >
        <div className="flex w-full items-center gap-2">
          <LayoutTemplate
            size={13}
            className={isActive ? 'text-brand' : 'text-ink-3'}
          />
          <span
            className={[
              'flex-1 truncate text-[12px] font-medium',
              isActive ? 'text-brand' : 'text-ink-1',
            ].join(' ')}
          >
            {label}
          </span>
          {isActive && (
            <Check size={11} className="flex-shrink-0 text-brand" />
          )}
        </div>
        <span className="text-[10.5px] text-ink-4">{sub}</span>
      </button>
    );
  };

  return (
    <div className="mt-1 space-y-2.5 rounded-lg border border-line-subtle bg-sunken/20 px-4 py-3">
      {/* Built-ins + no-template */}
      <div>
        <p className="mb-1.5 text-[11px] font-medium text-ink-3">内置模板</p>
        <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
          <Card t={null} />
          {builtins.map((t) => (
            <Card key={t.id} t={t} />
          ))}
        </div>
      </div>
      {/* User uploads */}
      {custom.length > 0 && (
        <div>
          <p className="mb-1.5 text-[11px] font-medium text-ink-3">我的模板</p>
          <div className="grid grid-cols-2 gap-1.5 sm:grid-cols-4">
            {custom.map((t) => (
              <Card key={t.id} t={t} />
            ))}
          </div>
        </div>
      )}
      {/* Upload button */}
      <button
        type="button"
        disabled={uploading}
        onClick={handleFilePick}
        className="flex items-center gap-1.5 text-[11.5px] text-ink-3 hover:text-ink-1 disabled:opacity-50"
      >
        <Upload size={12} />
        {uploading ? '上传中…' : '上传自定义模板（.docx / .pptx）'}
      </button>
    </div>
  );
};

// ----------------------------- My reports row ----------------------------

const ReportRow: React.FC<{ report: Report; onOpen: () => void }> = ({
  report,
  onOpen,
}) => {
  const tone = REPORT_STATUS_TONE[report.status] || 'neutral';
  const label = REPORT_STATUS_LABELS[report.status] || report.status;
  const active = REPORT_STATUS_ACTIVE.has(report.status);

  return (
    <button
      onClick={onOpen}
      className="group flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left transition-colors hover:bg-sunken/60"
    >
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] font-medium text-ink-1">
          {report.title}
        </p>
        <p className="mt-0.5 truncate text-[11.5px] text-ink-3">
          {formatDate(report.updated_at)} ·{' '}
          {Math.round((report.progress || 0) * 100)}%
        </p>
      </div>
      <Badge tone={tone} variant="soft" size="xs" dot pulsing={active}>
        {label}
      </Badge>
      <ArrowRight
        size={14}
        className="flex-shrink-0 text-ink-4 transition-transform group-hover:translate-x-0.5 group-hover:text-ink-2"
      />
    </button>
  );
};

// ----------------------------- Custom Report Type dialog -----------------

const CustomTypeDialog: React.FC<{
  open: boolean;
  onClose: () => void;
  onActivated: (id: string) => void;
}> = ({ open, onClose, onActivated }) => {
  const queryClient = useQueryClient();
  const [step, setStep] = useState<'input' | 'review'>('input');
  const [label, setLabel] = useState('');
  const [description, setDescription] = useState('');
  const [visibility, setVisibility] = useState<'private' | 'public'>('private');
  const [draft, setDraft] = useState<CustomRT | null>(null);

  // Reset when the dialog opens fresh.
  useEffect(() => {
    if (open) {
      setStep('input');
      setLabel('');
      setDescription('');
      setVisibility('private');
      setDraft(null);
    }
  }, [open]);

  const createMut = useMutation({
    mutationFn: () =>
      createCustomReportType({
        label: label.trim(),
        description: description.trim(),
        visibility,
      }),
    onSuccess: (rt) => {
      setDraft(rt);
      setStep('review');
    },
    onError: (err: any) =>
      toast.error(getApiErrorMessage(err, '创建失败')),
  });

  const reimproveMut = useMutation({
    mutationFn: () => reimproveCustomReportType(draft!.raw_id),
    onSuccess: (rt) => {
      setDraft(rt);
      toast.success('已重新生成');
    },
    onError: () => toast.error('重新生成失败'),
  });

  const confirmMut = useMutation({
    mutationFn: () =>
      confirmCustomReportType(draft!.raw_id, {
        label: draft!.label,
        improved_description: draft!.description,
        typical_output: draft!.typical_output,
        section_skeleton: draft!.section_skeleton,
        default_team: draft!.default_team,
        visibility: draft!.visibility,
      }),
    onSuccess: (rt) => {
      toast.success('模板已激活，可以用于创建报告了');
      queryClient.invalidateQueries({ queryKey: ['report-types'] });
      onActivated(rt.id);
      onClose();
    },
    onError: () => toast.error('激活失败'),
  });

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title={step === 'input' ? '自定义报告类型' : '确认模板骨架'}
      size="lg"
    >
      {step === 'input' && (
        <div className="flex flex-col gap-4">
          <div>
            <label className="text-[12px] font-semibold text-ink-2">
              报告类型名称
            </label>
            <Input
              value={label}
              onChange={(e) => setLabel(e.target.value)}
              placeholder="例如：客户尽调报告 / 投后月报"
              autoFocus
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-[12px] font-semibold text-ink-2">
              需求描述
            </label>
            <Textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="告诉我们这份报告是做什么的、给谁看的、关注哪些问题、希望有哪些章节。越详细我们改进得越准。"
              minRows={5}
              maxRows={10}
              className="mt-1"
            />
          </div>
          <div>
            <p className="text-[12px] font-semibold text-ink-2">可见性</p>
            <div className="mt-1.5 flex gap-2">
              {(['private', 'public'] as const).map((v) => (
                <button
                  key={v}
                  type="button"
                  onClick={() => setVisibility(v)}
                  className={[
                    'flex-1 rounded-md border px-3 py-2 text-left text-[12px] transition-all',
                    visibility === v
                      ? 'border-brand bg-brand-soft/40 ring-1 ring-brand/30'
                      : 'border-line hover:border-line-strong',
                  ].join(' ')}
                >
                  <div className="flex items-center gap-1.5 font-semibold text-ink-1">
                    {v === 'private' ? (
                      <>
                        <Eye size={12} />
                        仅自己可见
                      </>
                    ) : (
                      <>
                        <Users2 size={12} />
                        全员可用
                      </>
                    )}
                  </div>
                  <p className="mt-0.5 text-[11px] text-ink-3">
                    {v === 'private'
                      ? '只有你能用这个模板创建报告。'
                      : '任何人都能用这个模板创建报告（需激活）。'}
                  </p>
                </button>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between gap-2 pt-1">
            <p className="text-[11px] text-ink-3">
              我们会用大模型自动改进描述、生成章节骨架与员工阵容，改进后由你确认。
            </p>
            <Button
              size="sm"
              variant="primary"
              leftIcon={<Wand2 size={12} />}
              loading={createMut.isPending}
              disabled={!label.trim()}
              onClick={() => createMut.mutate()}
            >
              智能改进
            </Button>
          </div>
        </div>
      )}

      {step === 'review' && draft && (
        <div className="flex flex-col gap-4">
          <div>
            <label className="text-[12px] font-semibold text-ink-2">
              名称
            </label>
            <Input
              value={draft.label}
              onChange={(e) => setDraft({ ...draft, label: e.target.value })}
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-[12px] font-semibold text-ink-2">
              改进后描述
            </label>
            <Textarea
              value={draft.description}
              onChange={(e) =>
                setDraft({ ...draft, description: e.target.value })
              }
              minRows={3}
              maxRows={8}
              className="mt-1"
            />
          </div>
          <div>
            <label className="text-[12px] font-semibold text-ink-2">
              典型输出
            </label>
            <Input
              value={draft.typical_output}
              onChange={(e) =>
                setDraft({ ...draft, typical_output: e.target.value })
              }
              className="mt-1"
            />
          </div>
          <div>
            <div className="flex items-center justify-between">
              <label className="text-[12px] font-semibold text-ink-2">
                章节骨架 · {draft.section_skeleton.length}
              </label>
              <button
                type="button"
                onClick={() =>
                  setDraft({
                    ...draft,
                    section_skeleton: [
                      ...draft.section_skeleton,
                      {
                        id: `section_${draft.section_skeleton.length + 1}`,
                        title: '新章节',
                        kind: 'narrative',
                      },
                    ],
                  })
                }
                className="text-[11px] text-brand hover:underline"
              >
                + 增加章节
              </button>
            </div>
            <div className="mt-1.5 flex flex-col gap-1.5">
              {draft.section_skeleton.map((s, i) => (
                <div
                  key={i}
                  className="flex items-center gap-2 rounded-md border border-line-subtle bg-surface px-2.5 py-1.5"
                >
                  <span className="text-[11px] font-mono text-ink-4">
                    #{i + 1}
                  </span>
                  <input
                    value={s.title}
                    onChange={(e) => {
                      const next = [...draft.section_skeleton];
                      next[i] = { ...s, title: e.target.value };
                      setDraft({ ...draft, section_skeleton: next });
                    }}
                    className="flex-1 bg-transparent text-[12.5px] text-ink-1 outline-none"
                  />
                  <button
                    type="button"
                    onClick={() => {
                      const next = draft.section_skeleton.filter(
                        (_, idx) => idx !== i,
                      );
                      setDraft({ ...draft, section_skeleton: next });
                    }}
                    className="text-ink-4 hover:text-danger"
                    aria-label="删除章节"
                  >
                    <Trash2 size={12} />
                  </button>
                </div>
              ))}
            </div>
          </div>
          <div>
            <p className="text-[12px] font-semibold text-ink-2">
              默认阵容 · {draft.default_team.length} 位员工
            </p>
            <div className="mt-1.5 flex flex-wrap gap-1.5">
              {draft.default_team.map((id) => (
                <span
                  key={id}
                  className="flex items-center gap-1 rounded-full border border-line-subtle bg-sunken/40 px-2 py-0.5 text-[11px] font-mono text-ink-2"
                >
                  {id}
                </span>
              ))}
            </div>
          </div>
          <div className="flex items-center justify-between gap-2 border-t border-line-subtle pt-3">
            <Button
              size="sm"
              variant="ghost"
              leftIcon={<Wand2 size={12} />}
              loading={reimproveMut.isPending}
              onClick={() => reimproveMut.mutate()}
            >
              重新生成
            </Button>
            <div className="flex gap-2">
              <Button size="sm" variant="outline" onClick={onClose}>
                稍后再说
              </Button>
              <Button
                size="sm"
                variant="primary"
                leftIcon={<Check size={12} />}
                loading={confirmMut.isPending}
                onClick={() => confirmMut.mutate()}
              >
                确认并激活
              </Button>
            </div>
          </div>
        </div>
      )}
    </Dialog>
  );
};

// ============================= Page ======================================

export const HomePage: React.FC = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { isAuthenticated, openLoginModal } = useAuthStore();
  const { setReports, setCurrentReport, upsertReport } = useReportStore();

  // -------- Data --------
  const typesQ = useQuery({
    queryKey: ['report-types'],
    queryFn: listReportTypes,
    staleTime: 60 * 60 * 1000,
  });
  const workforceQ = useQuery({
    queryKey: ['workforce'],
    queryFn: getWorkforce,
    enabled: isAuthenticated,
    staleTime: 10 * 60 * 1000,
  });
  const reportsQ = useQuery({
    queryKey: ['reports', 'my'],
    queryFn: () => listReports({ limit: 8 }),
    enabled: isAuthenticated,
    staleTime: 5 * 1000,
  });

  useEffect(() => {
    if (reportsQ.data) setReports(reportsQ.data.items);
  }, [reportsQ.data, setReports]);

  // -------- Form state --------
  const [reportType, setReportType] = useState<ReportType | 'auto'>('auto');
  const [brief, setBrief] = useState('');
  const [uploading, setUploading] = useState(false);
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [skipConfirm, setSkipConfirm] = useState(false);
  const [customDialogOpen, setCustomDialogOpen] = useState(false);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [templatePickerOpen, setTemplatePickerOpen] = useState(false);
  const [templateUploading, setTemplateUploading] = useState(false);

  const templatesQ = useQuery({
    queryKey: ['templates'],
    queryFn: listTemplates,
    staleTime: 5 * 60 * 1000,
    enabled: isAuthenticated,
  });

  const handleTemplateUpload = async (file: File) => {
    setTemplateUploading(true);
    try {
      const t = await uploadTemplate(file);
      queryClient.invalidateQueries({ queryKey: ['templates'] });
      setSelectedTemplateId(t.id);
      toast.success(`模板 "${t.original_name}" 上传成功`);
    } catch {
      toast.error('模板上传失败');
    } finally {
      setTemplateUploading(false);
    }
  };

  // Default to auto-detect
  // (No override needed — useState default is 'auto')

  const selectedType = useMemo(
    () => typesQ.data?.items.find((t) => t.id === reportType),
    [typesQ.data, reportType],
  );
  // The actual report_type sent to the API ('auto' → 'internal_research' as fallback,
  // Chief's scoping prompt will auto-detect from brief when type is 'auto')
  const effectiveReportType = reportType === 'auto' ? 'auto' : reportType;

  // -------- Submit --------
  const createMut = useMutation({
    mutationFn: async () => {
      const fileIds = files
        .map((f) => Number(f.id))
        .filter((id) => Number.isInteger(id) && id > 0);

      if (files.length > 0 && fileIds.length !== files.length) {
        throw new Error('有文件尚未完成上传或文件 ID 无效，请移除后重新上传');
      }

      return createReport({
        brief: brief.trim(),
        report_type: effectiveReportType,
        file_ids: fileIds,
        template_file_id: selectedTemplateId ?? undefined,
        skip_clarifications: skipConfirm,
        auto_start: skipConfirm,
      });
    },
    onSuccess: (report) => {
      const seededReport: ReportDetail = {
        ...report,
        messages: [],
        clarifications: [],
        timeline: [],
        team_roster: report.team_roster ?? [],
        section_outline: report.section_outline ?? [],
        output_index: report.output_index ?? {},
      };
      setCurrentReport(seededReport);
      upsertReport(report);
      queryClient.invalidateQueries({ queryKey: ['reports', 'my'] });
      queryClient.invalidateQueries({ queryKey: ['report-types'] });
      queryClient.invalidateQueries({ queryKey: ['report', report.id] });
      toast.success(
        skipConfirm
          ? 'Chief 已直接开工'
          : '已创建协作室，先确认关键问题后再开始生产',
      );
      navigate(`/reports/${report.id}`);
    },
    onError: (err: any) => {
      toast.error(getApiErrorMessage(err, '创建报告失败'));
    },
  });

  // -------- File upload --------
  const handleFiles = async (fileList: FileList | null) => {
    if (!fileList || fileList.length === 0) return;
    if (!isAuthenticated) {
      openLoginModal();
      return;
    }
    setUploading(true);
    for (const f of Array.from(fileList)) {
      if (f.size > FILE_SIZE_LIMIT) {
        toast.error(`${f.name} 超过 ${FILE_SIZE_LIMIT / 1024 / 1024}MB`);
        continue;
      }
      try {
        const uploaded = await uploadFile(f);
        setFiles((prev) => [...prev, uploaded]);
      } catch (err: any) {
        toast.error(`${f.name} 上传失败`);
      }
    }
    setUploading(false);
  };

  const acceptStr = useMemo(
    () => {
      const extensions: string[] = [];
      Object.keys(ACCEPTED_FILE_TYPES).forEach((mime) => {
        const list = ACCEPTED_FILE_TYPES[mime as keyof typeof ACCEPTED_FILE_TYPES];
        list.forEach((ext) => extensions.push(ext));
      });
      return extensions.join(',') + ',.wps,.et,.dps';
    },
    [],
  );

  const canSubmit =
    brief.trim().length >= 6 && !createMut.isPending && isAuthenticated;

  // ----------------------- Layout -----------------------
  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto flex max-w-[1040px] flex-col gap-10 px-6 pb-20 pt-10">
        {/* -------- Hero -------- */}
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
          className="flex flex-col gap-3"
        >
          <div className="flex items-center gap-2 text-[11.5px] uppercase tracking-[0.2em] text-ink-3">
            <Sparkles size={12} className="text-brand" />
            新建报告 · Compose
          </div>
          <h1 className="font-serif text-[28px] font-semibold leading-tight text-ink-1">
            把你的需求交给 Chief,让团队开工。
          </h1>
          <p className="max-w-[680px] text-[14px] leading-relaxed text-ink-2">
            这不是一个问答系统。你描述想要的报告,Chief
            会组织员工按章节生产,并在必要时回来问你一两个关键问题。
          </p>
        </motion.div>

        {/* -------- Compose card -------- */}
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25, delay: 0.05 }}
          className="overflow-hidden rounded-xl border border-line bg-surface shadow-sm"
        >
          {/* Chief strip */}
          <div className="flex items-center justify-between border-b border-line-subtle bg-sunken/30 px-5 py-3">
            <ChiefAvatar supervisor={workforceQ.data?.supervisor} />
            <span className="text-caption uppercase tracking-[0.18em] text-ink-3">
              委托 Chief
            </span>
          </div>

          {/* Brief input */}
          <div className="px-5 pt-5">
            <Textarea
              value={brief}
              onChange={(e) => setBrief(e.target.value)}
              placeholder="例如:请基于我上传的 Q1 经营数据,写一份零售业务条线的经营分析报告,聚焦收入与不良率变化,并给出下季度行动建议…"
              autoResize
              minRows={4}
              maxRows={12}
              className="text-[14.5px] leading-relaxed"
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter' && canSubmit) {
                  createMut.mutate();
                }
              }}
            />
            <p className="mt-1.5 text-[11.5px] text-ink-4">
              用 ⌘/Ctrl + Enter 直接交给 Chief。
            </p>
          </div>

          {/* Upload strip */}
          <div className="px-5 pt-3">
            <label
              className={[
                'flex cursor-pointer items-center gap-2 rounded-md border border-dashed px-3 py-2 text-[12.5px] transition-colors',
                uploading
                  ? 'border-brand/50 bg-brand-soft/30 text-brand'
                  : 'border-line-subtle text-ink-3 hover:border-line-strong hover:bg-sunken/50 hover:text-ink-2',
              ].join(' ')}
            >
              <Paperclip size={13} />
              <span>
                {uploading
                  ? '上传中…'
                  : '附加材料(PDF / Word / Excel / PPT / WPS / 扫描件)'}
              </span>
              <input
                type="file"
                multiple
                accept={acceptStr}
                className="hidden"
                onChange={(e) => {
                  handleFiles(e.target.files);
                  e.target.value = '';
                }}
              />
            </label>

            {files.length > 0 && (
              <div className="mt-2.5 flex flex-wrap gap-2">
                {files.map((f) => (
                  <span
                    key={f.id}
                    className="flex items-center gap-1.5 rounded-md border border-line-subtle bg-sunken/40 px-2.5 py-1 text-[11.5px] text-ink-2"
                  >
                    <FileText size={11} className="text-ink-3" />
                    <span className="max-w-[180px] truncate">
                      {f.original_name}
                    </span>
                    <span className="text-ink-4">
                      {formatFileSize(f.file_size)}
                    </span>
                    <button
                      type="button"
                      onClick={() =>
                        setFiles((prev) => prev.filter((x) => x.id !== f.id))
                      }
                      className="text-ink-4 hover:text-danger"
                    >
                      <X size={11} />
                    </button>
                  </span>
                ))}
              </div>
            )}
          </div>

          {/* Report type selection */}
          <div className="px-5 pt-5">
            <div className="mb-2 flex items-center justify-between">
              <p className="flex items-center gap-1.5 text-caption font-semibold uppercase tracking-[0.16em] text-ink-3">
                <Sparkles size={11} />
                报告类型
              </p>
              <button
                type="button"
                onClick={() => {
                  if (!isAuthenticated) { openLoginModal(); return; }
                  setCustomDialogOpen(true);
                }}
                className="flex items-center gap-1 text-[11.5px] font-medium text-brand hover:underline"
              >
                <Plus size={11} />
                自定义报告类型
              </button>
            </div>
            {typesQ.isLoading ? (
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
                {[0,1,2,3,4].map((i) => <Skeleton key={i} className="h-[72px] rounded-lg" />)}
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2 lg:grid-cols-3">
                {/* Auto-detect chip */}
                <button
                  type="button"
                  onClick={() => setReportType('auto' as ReportType)}
                  className={[
                    'group flex flex-col items-start gap-1 rounded-lg border p-3 text-left transition-all',
                    reportType === 'auto'
                      ? 'border-brand/70 bg-brand-soft/40 ring-1 ring-brand/30'
                      : 'border-line bg-surface hover:border-line-strong hover:bg-sunken/40',
                  ].join(' ')}
                >
                  <div className="flex w-full items-center justify-between">
                    <span className={['flex items-center gap-1.5 text-[13px] font-semibold', reportType === 'auto' ? 'text-brand' : 'text-ink-1'].join(' ')}>
                      <Wand2 size={12} />
                      自动识别
                    </span>
                    <span className="text-caption text-ink-4">Auto</span>
                  </div>
                  <p className="text-[11.5px] leading-relaxed text-ink-3">Chief 根据描述和文件自动推断最合适的类型</p>
                </button>
                {typesQ.data?.items.map((t) => (
                  <TypeChip key={t.id} info={t} active={reportType === t.id} onClick={() => setReportType(t.id)} />
                ))}
              </div>
            )}
          </div>

          {/* Type preview */}
          {selectedType && (
            <div className="mx-5 mt-4 rounded-lg border border-line-subtle bg-sunken/30 px-4 py-3">
              <p className="text-[11.5px] uppercase tracking-[0.16em] text-ink-3">
                预设产出
              </p>
              <p className="mt-1 text-[12.5px] font-medium text-ink-1">
                {selectedType.typical_output}
              </p>
              <p className="mt-1 text-[11.5px] text-ink-3">
                章节骨架:
                {selectedType.section_skeleton
                  .map((s) => s.title)
                  .join(' · ')}
              </p>
              <p className="mt-1 text-[11.5px] text-ink-3">
                默认阵容: {selectedType.default_team.length} 名员工 + Chief
              </p>
            </div>
          )}

          {/* Output template picker (first) */}
          {isAuthenticated && (
            <div className="mx-5 mt-4">
              <div className="mb-1.5 flex items-center gap-1.5">
                <LayoutTemplate size={11} className="text-ink-3" />
                <p className="text-caption font-semibold uppercase tracking-[0.16em] text-ink-3">输出模板</p>
              </div>
              <button
                type="button"
                onClick={() => setTemplatePickerOpen((v) => !v)}
                className="flex w-full items-center gap-1.5 rounded-lg border border-line bg-surface px-3 py-2 text-[12px] text-ink-2 transition-colors hover:border-line-strong hover:bg-sunken/40"
              >
                <span className="flex-1 text-left">
                  {selectedTemplateId
                    ? (templatesQ.data?.find((t) => t.id === selectedTemplateId)?.original_name ?? '已选模板')
                    : '默认样式（不使用模板）'}
                </span>
                <ChevronDown size={12} className={templatePickerOpen ? 'rotate-180 text-brand transition-transform' : 'text-ink-4 transition-transform'} />
              </button>
              {templatePickerOpen && (
                <TemplatePickerPanel
                  templates={templatesQ.data ?? []}
                  selected={selectedTemplateId}
                  onSelect={(id) => { setSelectedTemplateId(id); setTemplatePickerOpen(false); }}
                  onUpload={handleTemplateUpload}
                  uploading={templateUploading}
                />
              )}
            </div>
          )}

          {/* Skip-confirmation toggle (second) */}
          {isAuthenticated && (
            <div className="mx-5 mt-3 flex items-start gap-3 rounded-lg border border-line-subtle bg-sunken/20 px-4 py-3">
              <button
                type="button"
                onClick={() => setSkipConfirm((v) => !v)}
                className={['mt-0.5 flex h-4 w-7 flex-shrink-0 items-center rounded-full border transition-colors', skipConfirm ? 'border-brand bg-brand' : 'border-line bg-sunken'].join(' ')}
                role="switch"
                aria-checked={skipConfirm}
              >
                <span className={['h-3 w-3 rounded-full bg-white shadow-sm transition-transform', skipConfirm ? 'translate-x-[14px]' : 'translate-x-0.5'].join(' ')} />
              </button>
              <div className="min-w-0 flex-1">
                <p className="flex items-center gap-1.5 text-[12.5px] font-medium text-ink-1">
                  <Play size={11} className="text-ink-3" />
                  无需再交流，直接开始生成
                </p>
                <p className="mt-0.5 text-[11.5px] leading-relaxed text-ink-3">
                  开启后，Chief 不再提问；澄清问题按默认答案处理，直接进入生产。
                </p>
              </div>
            </div>
          )}

          {/* Footer actions */}
          <div className="mt-4 flex items-center justify-between border-t border-line-subtle bg-sunken/20 px-5 py-3">
            <p className="text-[11.5px] text-ink-3">
              {isAuthenticated ? (
                skipConfirm ? (
                  <>直接开工模式：Chief 不再提问，提交后即进入生产。</>
                ) : (
                  <>Chief 将先确认 1-2 个关键问题；确认后再由你决定开始生产。</>
                )
              ) : (
                <>请先登录以使用报告生产系统。</>
              )}
            </p>
            {isAuthenticated ? (
              <Button
                variant="supervisor"
                size="md"
                rightIcon={<Play size={13} />}
                loading={createMut.isPending}
                disabled={!canSubmit}
                onClick={() => createMut.mutate()}
              >
                {skipConfirm ? '直接生成' : '交给 Chief'}
              </Button>
            ) : (
              <Button variant="primary" size="md" onClick={() => openLoginModal()}>
                登录后开始
              </Button>
            )}
          </div>
        </motion.div>

        {/* -------- Custom report type dialog -------- */}
        <CustomTypeDialog
          open={customDialogOpen}
          onClose={() => setCustomDialogOpen(false)}
          onActivated={(id) => setReportType(id)}
        />

        {/* -------- My reports -------- */}
        {isAuthenticated && (
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25, delay: 0.1 }}
            className="flex flex-col gap-3"
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Clock size={14} className="text-ink-3" />
                <h2 className="text-[14px] font-semibold text-ink-1">
                  最近的报告
                </h2>
              </div>
              <button
                onClick={() => navigate('/archive')}
                className="text-[12px] text-ink-3 hover:text-ink-1"
              >
                查看全部 →
              </button>
            </div>

            {reportsQ.isLoading ? (
              <div className="flex flex-col gap-1">
                {[0, 1, 2].map((i) => (
                  <Skeleton key={i} className="h-[48px] rounded-md" />
                ))}
              </div>
            ) : reportsQ.data && reportsQ.data.items.length > 0 ? (
              <div className="overflow-hidden rounded-lg border border-line-subtle bg-surface">
                {reportsQ.data.items.map((r, i) => (
                  <div
                    key={r.id}
                    className={
                      i > 0 ? 'border-t border-line-subtle' : undefined
                    }
                  >
                    <ReportRow
                      report={r}
                      onOpen={() => navigate(`/reports/${r.id}`)}
                    />
                  </div>
                ))}
              </div>
            ) : (
              <div className="rounded-lg border border-dashed border-line-subtle">
                <EmptyState
                  compact
                  icon={<FileText size={16} />}
                  title="还没有报告"
                  description="在上面的输入框里把任务交给 Chief 试试。"
                />
              </div>
            )}
          </motion.div>
        )}
      </div>
    </div>
  );
};

export default HomePage;
