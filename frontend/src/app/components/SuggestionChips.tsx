import { Award, Calendar, BarChart3, PieChart, FileSearch, GraduationCap } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

export interface ScenarioSuggestion {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  placeholder: string;
  color: string;
  bg: string;
  agent: "docs" | "ppt" | "sheet";
  outputFormat: "word" | "pptx" | "xlsx";
  reportType: string;
  skills: string[];
}

const suggestions: ScenarioSuggestion[] = [
  {
    icon: Award,
    label: "年终述职",
    placeholder: "例如：帮我整理 2025 年的工作成果，生成年终述职报告...",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "述职报告",
    skills: ["performance-review-authoring"],
  },
  {
    icon: Calendar,
    label: "季度总结",
    placeholder: "例如：总结 Q4 的项目进展和关键数据，生成季度总结文档...",
    color: "#2563eb",
    bg: "rgba(37,99,235,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "述职报告",
    skills: ["performance-review-authoring"],
  },
  {
    icon: BarChart3,
    label: "分析数据",
    placeholder: "例如：分析这份销售数据，找出增长趋势和异常点...",
    color: "#059669",
    bg: "rgba(5,150,105,0.10)",
    agent: "sheet",
    outputFormat: "xlsx",
    reportType: "数据分析",
    skills: ["data-grounding", "excel-modeling", "advanced-charting"],
  },
  {
    icon: PieChart,
    label: "生成图表",
    placeholder: "例如：根据上传的数据生成可视化图表，展示各部门占比...",
    color: "#8b5cf6",
    bg: "rgba(139,92,246,0.10)",
    agent: "sheet",
    outputFormat: "xlsx",
    reportType: "图表分析",
    skills: ["data-grounding", "advanced-charting", "table-figure-authoring"],
  },
  {
    icon: FileSearch,
    label: "研究报告",
    placeholder: "例如：撰写一份关于 AI 行业趋势的研究报告，包含数据分析...",
    color: "#ec4899",
    bg: "rgba(236,72,153,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "研究报告",
    skills: ["research-report-authoring", "executive-summary"],
  },
  {
    icon: GraduationCap,
    label: "论文写作",
    placeholder: "例如：帮我撰写一篇关于机器学习应用的学术论文...",
    color: "#06b6d4",
    bg: "rgba(6,182,212,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "学术论文",
    skills: ["academic-paper-authoring", "citation-bibliography"],
  },
];

const ROTATE_MS = 8600;
const PAGE_SIZE = 6;
const suggestionPool: ScenarioSuggestion[] = [
  ...suggestions,
  {
    icon: Award,
    label: "项目复盘",
    placeholder: "例如：复盘重点项目的目标、过程、结果和改进建议...",
    color: "#dc2626",
    bg: "rgba(220,38,38,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "项目复盘",
    skills: ["project-retrospective-authoring"],
  },
  {
    icon: BarChart3,
    label: "经营分析",
    placeholder: "例如：生成经营分析报告，包含收入、成本、利润和风险提示...",
    color: "#0f766e",
    bg: "rgba(15,118,110,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "经营分析",
    skills: ["business-document-authoring", "executive-summary"],
  },
  {
    icon: FileSearch,
    label: "竞品调研",
    placeholder: "例如：整理竞品调研报告，对比定位、功能、价格和机会点...",
    color: "#7c3aed",
    bg: "rgba(124,58,237,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "研究报告",
    skills: ["research-report-authoring", "executive-summary"],
  },
  {
    icon: Calendar,
    label: "会议纪要",
    placeholder: "例如：根据会议记录生成纪要，提炼结论、负责人和待办事项...",
    color: "#0891b2",
    bg: "rgba(8,145,178,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "会议纪要",
    skills: ["meeting-minutes-authoring"],
  },
  {
    icon: PieChart,
    label: "预算汇报",
    placeholder: "例如：整理预算执行情况，输出偏差分析和下一步建议...",
    color: "#b45309",
    bg: "rgba(180,83,9,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "经营分析",
    skills: ["business-document-authoring", "advanced-charting", "table-figure-authoring"],
  },
  {
    icon: GraduationCap,
    label: "培训材料",
    placeholder: "例如：生成内部培训材料，包含课程目标、知识点和测验题...",
    color: "#16a34a",
    bg: "rgba(22,163,74,0.10)",
    agent: "docs",
    outputFormat: "word",
    reportType: "培训手册",
    skills: ["training-manual-authoring"],
  },
];

export function SuggestionChips({ onSelect }: { onSelect?: (scenario: ScenarioSuggestion) => void }) {
  const [page, setPage] = useState(0);
  const totalPages = Math.ceil(suggestionPool.length / PAGE_SIZE);
  const visible = useMemo(() => {
    const start = (page % totalPages) * PAGE_SIZE;
    return suggestionPool.slice(start, start + PAGE_SIZE);
  }, [page, totalPages]);

  useEffect(() => {
    const timer = window.setInterval(() => setPage((p) => (p + 1) % totalPages), ROTATE_MS);
    return () => window.clearInterval(timer);
  }, [totalPages]);

  return (
    <div className="w-full mt-3" key={page}>
      <style>{`
        @keyframes chip-pop-up {
          from {
            opacity: 0;
            transform: translateY(10px) scale(0.96);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
        @keyframes chip-fade-bloom {
          from { opacity: 0; transform: translateY(8px) scale(0.94); }
          55% { opacity: 1; transform: translateY(-2px) scale(1.035); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .chip-animated {
          animation: chip-fade-bloom 0.52s cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
        }
      `}</style>
      <div className="flex flex-wrap gap-2 justify-center">
        {visible.map((item, index) => {
          const Icon = item.icon;
          return (
            <button
              key={item.label}
              onClick={() => onSelect?.(item)}
              className="chip-animated inline-flex items-center gap-1.5 px-3 py-1.5 rounded-md transition-all"
              style={{
                background: "transparent",
                border: "1px solid var(--border)",
                color: "var(--ink-500)",
                fontSize: "12.5px",
                fontWeight: 500,
                animationDelay: `${0.2 + index * 0.08}s`,
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "var(--bg-subtle)";
                e.currentTarget.style.borderColor = "var(--border-strong)";
                e.currentTarget.style.color = "var(--ink-900)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "transparent";
                e.currentTarget.style.borderColor = "var(--border)";
                e.currentTarget.style.color = "var(--ink-500)";
              }}
            >
              <Icon className="h-3.5 w-3.5" />
              {item.label}
            </button>
          );
        })}
      </div>
    </div>
  );
}
