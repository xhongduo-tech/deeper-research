import { create } from 'zustand';
import type { Report, ReportDetail, ReportMessage, Clarification, TimelineEvent } from '../types/report';

function normalizeReportDetail(r: ReportDetail): ReportDetail {
  return {
    ...r,
    messages: Array.isArray(r.messages) ? r.messages : [],
    clarifications: Array.isArray(r.clarifications) ? r.clarifications : [],
    timeline: Array.isArray(r.timeline) ? r.timeline : [],
    team_roster: Array.isArray(r.team_roster) ? r.team_roster : r.team_roster ?? [],
    section_outline: Array.isArray(r.section_outline) ? r.section_outline : r.section_outline ?? [],
    output_index:
      r.output_index && typeof r.output_index === 'object' ? r.output_index : {},
  };
}

interface ReportStoreState {
  // Sidebar history
  reports: Report[];
  setReports: (reports: Report[]) => void;
  upsertReport: (r: Report) => void;
  removeReport: (id: number) => void;

  // Currently-open report
  currentReport: ReportDetail | null;
  setCurrentReport: (r: ReportDetail | null) => void;

  // Live streaming updates into current report
  applyStatusPatch: (patch: Partial<Report>) => void;
  applySectionOutput: (sectionId: string, output: import('../types/report').OutputSection) => void;
  appendMessage: (m: ReportMessage) => void;
  upsertClarification: (c: Clarification) => void;
  appendTimeline: (t: TimelineEvent) => void;
}

export const useReportStore = create<ReportStoreState>((set) => ({
  reports: [],
  setReports: (reports) => set({ reports }),
  upsertReport: (r) =>
    set((s) => {
      const idx = s.reports.findIndex((x) => x.id === r.id);
      if (idx === -1) return { reports: [r, ...s.reports] };
      const next = [...s.reports];
      next[idx] = { ...next[idx], ...r };
      return { reports: next };
    }),
  removeReport: (id) =>
    set((s) => ({ reports: s.reports.filter((r) => r.id !== id) })),

  currentReport: null,
  setCurrentReport: (r) => set({ currentReport: r ? normalizeReportDetail(r) : null }),

  applyStatusPatch: (patch) =>
    set((s) => {
      if (!s.currentReport) return {};
      const updated = normalizeReportDetail({
        ...s.currentReport,
        ...patch,
      } as ReportDetail);
      // Also reflect in sidebar list
      const reports = s.reports.map((r) =>
        r.id === updated.id ? { ...r, ...patch } : r
      );
      return { currentReport: updated, reports };
    }),

  applySectionOutput: (sectionId, output) =>
    set((s) => {
      if (!s.currentReport) return {};
      const current: Record<string, import('../types/report').OutputSection> =
        (s.currentReport.output_index as Record<string, import('../types/report').OutputSection>) ?? {};
      return {
        currentReport: {
          ...s.currentReport,
          output_index: { ...current, [sectionId]: output },
        },
      };
    }),

  appendMessage: (m) =>
    set((s) => {
      if (!s.currentReport || s.currentReport.id !== m.report_id) return {};
      const existing = s.currentReport.messages ?? [];
      if (existing.some((x) => x.id === m.id)) return {};
      return {
        currentReport: {
          ...s.currentReport,
          messages: [...existing, m],
        },
      };
    }),

  upsertClarification: (c) =>
    set((s) => {
      if (!s.currentReport || s.currentReport.id !== c.report_id) return {};
      const list = s.currentReport.clarifications ?? [];
      const idx = list.findIndex((x) => x.id === c.id);
      const next = idx === -1 ? [...list, c] : list.map((x) => (x.id === c.id ? c : x));
      return {
        currentReport: {
          ...s.currentReport,
          clarifications: next,
        },
      };
    }),

  appendTimeline: (t) =>
    set((s) => {
      if (!s.currentReport || s.currentReport.id !== t.report_id) return {};
      const existing = s.currentReport.timeline ?? [];
      if (existing.some((x) => x.id === t.id)) return {};
      return {
        currentReport: {
          ...s.currentReport,
          timeline: [...existing, t],
        },
      };
    }),
}));
