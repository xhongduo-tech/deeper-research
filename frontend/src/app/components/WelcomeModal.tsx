/**
 * WelcomeModal — paginated first-visit onboarding.
 * 5 pages, one idea per page. Shown once (localStorage).
 */
import { useState, useEffect } from "react";
import { X, ArrowRight, ChevronLeft } from "lucide-react";

const STORAGE_KEY = "dataagent_welcome_v2_shown";

// ── Slide definitions ──────────────────────────────────────────────────────

const SLIDES = [
  {
    emoji: "🤖",
    color: "#2563eb",
    title: "多智能体深度研究",
    subtitle: "不只是问答，是完整的研究流程",
    desc: "输入一个课题，AI 自动规划任务、检索资料、核实信息，最终生成结构完整的 Word 报告，一键下载。",
  },
  {
    emoji: "🗄️",
    color: "#7c3aed",
    title: "私有数据库",
    subtitle: "让 AI 读懂你的内部文档",
    desc: "上传 PDF、Word、Excel 等内部文件，AI 向量化后作为研究的第一手资料，检索精准，不出内网。",
  },
  {
    emoji: "🕸️",
    color: "#0891b2",
    title: "知识图谱 & 情感分析",
    subtitle: "把文字里的关系和情绪可视化",
    desc: "自动提取实体关系、构建知识网络；同时分析文本情感极性与风险信号，洞察隐藏在字里行间的信息。",
  },
  {
    emoji: "⚡",
    color: "#d97706",
    title: "因果推理 & 逻辑评估",
    subtitle: "追问「为什么」，而不只是「是什么」",
    desc: "从现象追溯根因，检测逻辑漏洞与矛盾，自动挖掘论证结构——让研究结论更有说服力。",
  },
  {
    emoji: "🔒",
    color: "#16a34a",
    title: "内网安全部署",
    subtitle: "数据不离开你的网络",
    desc: "全栈本地化运行，对接私有 Ollama 模型，无外部数据传输。满足企业数据安全与合规要求。",
  },
];

// ── Component ──────────────────────────────────────────────────────────────

interface WelcomeModalProps {
  onClose: () => void;
  onLearnMore: () => void;
}

export function WelcomeModal({ onClose, onLearnMore }: WelcomeModalProps) {
  const [page, setPage] = useState(0);
  const [dir, setDir] = useState<1 | -1>(1);
  const [animKey, setAnimKey] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const t = requestAnimationFrame(() => setVisible(true));
    return () => cancelAnimationFrame(t);
  }, []);

  const goTo = (next: number, direction: 1 | -1 = 1) => {
    setDir(direction);
    setAnimKey((k) => k + 1);
    setPage(next);
  };

  const handleClose = () => {
    setVisible(false);
    setTimeout(onClose, 210);
  };

  const isLast = page === SLIDES.length - 1;
  const slide = SLIDES[page];

  return (
    <>
      {/* Backdrop */}
      <div
        onClick={handleClose}
        style={{
          position: "fixed", inset: 0, zIndex: 300,
          background: "rgba(0,0,0,0.48)",
          backdropFilter: "blur(4px)",
          WebkitBackdropFilter: "blur(4px)",
          opacity: visible ? 1 : 0,
          transition: "opacity 0.2s ease",
        }}
      />

      {/* Modal */}
      <div
        style={{
          position: "fixed", zIndex: 301,
          top: "50%", left: "50%",
          transform: visible
            ? "translate(-50%, -50%) scale(1)"
            : "translate(-50%, -50%) scale(0.94)",
          opacity: visible ? 1 : 0,
          transition: "transform 0.26s cubic-bezier(0.34,1.3,0.64,1), opacity 0.2s ease",
          width: "calc(100vw - 40px)",
          maxWidth: 480,
          borderRadius: 22,
          overflow: "hidden",
          background: "var(--bg)",
          border: "1px solid var(--border)",
          boxShadow: "0 28px 72px rgba(0,0,0,0.2)",
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Close */}
        <button
          onClick={handleClose}
          style={{
            position: "absolute", top: 14, right: 14, zIndex: 10,
            width: 28, height: 28, borderRadius: 8,
            display: "flex", alignItems: "center", justifyContent: "center",
            color: "var(--ink-400)", background: "transparent", border: "none", cursor: "pointer",
            transition: "background .15s",
          }}
          onMouseEnter={e => (e.currentTarget.style.background = "rgba(0,0,0,0.06)")}
          onMouseLeave={e => (e.currentTarget.style.background = "transparent")}
        >
          <X size={15} />
        </button>

        {/* Slide content */}
        <div
          key={animKey}
          style={{
            padding: "44px 36px 32px",
            animation: `slide-in-${dir > 0 ? "right" : "left"} 0.28s cubic-bezier(0.34,1.1,0.64,1) both`,
          }}
        >
          <style>{`
            @keyframes slide-in-right { from { opacity:0; transform:translateX(28px); } to { opacity:1; transform:none; } }
            @keyframes slide-in-left  { from { opacity:0; transform:translateX(-28px); } to { opacity:1; transform:none; } }
          `}</style>

          {/* Big emoji */}
          <div style={{
            width: 72, height: 72, borderRadius: 20,
            background: `${slide.color}12`,
            border: `1.5px solid ${slide.color}28`,
            display: "flex", alignItems: "center", justifyContent: "center",
            fontSize: 36, marginBottom: 24,
          }}>
            {slide.emoji}
          </div>

          {/* Text */}
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.07em", textTransform: "uppercase", color: slide.color, marginBottom: 6 }}>
            {slide.subtitle}
          </div>
          <h2 style={{ fontSize: 24, fontWeight: 700, letterSpacing: "-0.02em", color: "var(--ink-900)", margin: "0 0 12px", lineHeight: 1.2 }}>
            {slide.title}
          </h2>
          <p style={{ fontSize: 14.5, color: "var(--ink-500)", lineHeight: 1.75, margin: 0 }}>
            {slide.desc}
          </p>
        </div>

        {/* Footer */}
        <div style={{
          padding: "16px 28px 22px",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          gap: 12,
        }}>
          {/* Dot indicators */}
          <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
            {SLIDES.map((_, i) => (
              <button
                key={i}
                onClick={() => goTo(i, i > page ? 1 : -1)}
                style={{
                  width: i === page ? 18 : 6,
                  height: 6,
                  borderRadius: 99,
                  background: i === page ? slide.color : "var(--border)",
                  border: "none",
                  cursor: "pointer",
                  padding: 0,
                  transition: "width .25s ease, background .25s ease",
                }}
              />
            ))}
          </div>

          {/* Nav buttons */}
          <div style={{ display: "flex", gap: 8 }}>
            {page > 0 && (
              <button
                onClick={() => goTo(page - 1, -1)}
                style={{
                  padding: "8px 14px", borderRadius: 10,
                  border: "1px solid var(--border)",
                  background: "transparent",
                  fontSize: 13, fontWeight: 600, color: "var(--ink-500)",
                  cursor: "pointer", display: "flex", alignItems: "center", gap: 4,
                  transition: "border-color .15s",
                }}
                onMouseEnter={e => (e.currentTarget.style.borderColor = "var(--ink-400)")}
                onMouseLeave={e => (e.currentTarget.style.borderColor = "var(--border)")}
              >
                <ChevronLeft size={13} />
                上一步
              </button>
            )}

            {isLast ? (
              <button
                onClick={handleClose}
                style={{
                  padding: "8px 20px", borderRadius: 10,
                  background: slide.color,
                  border: "none",
                  fontSize: 13, fontWeight: 600, color: "#fff",
                  cursor: "pointer",
                  boxShadow: `0 2px 8px ${slide.color}44`,
                  display: "flex", alignItems: "center", gap: 5,
                  transition: "opacity .15s",
                }}
                onMouseEnter={e => (e.currentTarget.style.opacity = "0.85")}
                onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
              >
                开始体验
                <ArrowRight size={13} />
              </button>
            ) : (
              <button
                onClick={() => goTo(page + 1, 1)}
                style={{
                  padding: "8px 20px", borderRadius: 10,
                  background: slide.color,
                  border: "none",
                  fontSize: 13, fontWeight: 600, color: "#fff",
                  cursor: "pointer",
                  boxShadow: `0 2px 8px ${slide.color}44`,
                  display: "flex", alignItems: "center", gap: 5,
                  transition: "opacity .15s",
                }}
                onMouseEnter={e => (e.currentTarget.style.opacity = "0.85")}
                onMouseLeave={e => (e.currentTarget.style.opacity = "1")}
              >
                下一步
                <ArrowRight size={13} />
              </button>
            )}
          </div>
        </div>
      </div>
    </>
  );
}

// ── Hook ───────────────────────────────────────────────────────────────────

export function useWelcomeModal() {
  const [show, setShow] = useState(false);

  useEffect(() => {
    if (!localStorage.getItem(STORAGE_KEY)) {
      const t = setTimeout(() => setShow(true), 500);
      return () => clearTimeout(t);
    }
  }, []);

  const dismiss = () => {
    localStorage.setItem(STORAGE_KEY, "1");
    setShow(false);
  };

  return { show, dismiss };
}

export default WelcomeModal;
