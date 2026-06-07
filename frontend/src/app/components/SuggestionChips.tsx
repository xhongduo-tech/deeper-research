import { Award, Calendar, BarChart3, PieChart, FileSearch, GraduationCap } from "lucide-react";

export interface ScenarioSuggestion {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  placeholder: string;
  color: string;
  bg: string;
}

const suggestions: ScenarioSuggestion[] = [
  {
    icon: Award,
    label: "年终述职",
    placeholder: "例如：帮我整理 2025 年的工作成果，生成年终述职报告...",
    color: "#f59e0b",
    bg: "rgba(245,158,11,0.10)"
  },
  {
    icon: Calendar,
    label: "季度总结",
    placeholder: "例如：总结 Q4 的项目进展和关键数据，生成季度总结文档...",
    color: "#2563eb",
    bg: "rgba(37,99,235,0.10)"
  },
  {
    icon: BarChart3,
    label: "分析数据",
    placeholder: "例如：分析这份销售数据，找出增长趋势和异常点...",
    color: "#059669",
    bg: "rgba(5,150,105,0.10)"
  },
  {
    icon: PieChart,
    label: "生成图表",
    placeholder: "例如：根据上传的数据生成可视化图表，展示各部门占比...",
    color: "#8b5cf6",
    bg: "rgba(139,92,246,0.10)"
  },
  {
    icon: FileSearch,
    label: "研究报告",
    placeholder: "例如：撰写一份关于 AI 行业趋势的研究报告，包含数据分析...",
    color: "#ec4899",
    bg: "rgba(236,72,153,0.10)"
  },
  {
    icon: GraduationCap,
    label: "论文写作",
    placeholder: "例如：帮我撰写一篇关于机器学习应用的学术论文...",
    color: "#06b6d4",
    bg: "rgba(6,182,212,0.10)"
  },
];

export function SuggestionChips({ onSelect }: { onSelect?: (scenario: ScenarioSuggestion) => void }) {
  return (
    <div className="w-full mt-3">
      <style>{`
        @keyframes chip-pop-up {
          from {
            opacity: 0;
            transform: translateY(12px);
          }
          to {
            opacity: 1;
            transform: translateY(0);
          }
        }
        .chip-animated {
          animation: chip-pop-up 0.4s cubic-bezier(0.34, 1.56, 0.64, 1) backwards;
        }
      `}</style>
      <div className="flex flex-wrap gap-2 justify-center">
        {suggestions.map((item, index) => {
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
