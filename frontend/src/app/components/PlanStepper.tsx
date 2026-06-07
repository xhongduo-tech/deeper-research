/**
 * PlanStepper — animated vertical stepper for the task-planning phase.
 *
 * States:
 *   loading   → glowing indicator, "正在生成计划..."
 *   streaming → typewriter intro, collapsible Thinking block, plan steps fade in
 *   done      → green ✅ Done, connector line lights up
 */

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import {
  CheckCircle2,
  Circle,
  Loader2,
  ChevronRight,
  BrainCircuit,
} from "lucide-react";

// ─────────────────────────────────────────────────────────────────
// Utility (mirrors App.tsx's stripPlanStepNumber)
// ─────────────────────────────────────────────────────────────────
export function stripPlanStepNumber(value: string) {
  return String(value || "")
    .replace(/^\s*(?:\d+|[一二三四五六七八九十]+)[\.、\)]\s*/, "")
    .trim();
}

// ─────────────────────────────────────────────────────────────────
// TypingText — typewriter character-by-character reveal
// ─────────────────────────────────────────────────────────────────
interface TypingTextProps {
  text: string;
  speed?: number; // ms per char
  onDone?: () => void;
  className?: string;
  style?: React.CSSProperties;
  /** Skip animation and show full text immediately */
  instant?: boolean;
}

export function TypingText({
  text,
  speed = 16,
  onDone,
  className,
  style,
  instant = false,
}: TypingTextProps) {
  const [count, setCount] = useState(instant ? text.length : 0);
  const calledRef = useRef(false);

  // Reset when text changes
  useEffect(() => {
    setCount(instant ? text.length : 0);
    calledRef.current = false;
  }, [text, instant]);

  useEffect(() => {
    if (count >= text.length) {
      if (!calledRef.current) {
        calledRef.current = true;
        onDone?.();
      }
      return;
    }
    const t = setTimeout(() => setCount((n) => n + 1), speed);
    return () => clearTimeout(t);
  }, [count, text, speed, onDone]);

  return (
    <span className={className} style={style}>
      {text.slice(0, count)}
      {count < text.length && (
        <span
          className="inline-block align-middle animate-pulse"
          style={{
            width: 2,
            height: "0.9em",
            background: "currentColor",
            marginLeft: 1,
            borderRadius: 1,
            opacity: 0.6,
          }}
        />
      )}
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────
// ThinkingBlock — collapsible reasoning display
// ─────────────────────────────────────────────────────────────────
interface ThinkingBlockProps {
  content: string;
  defaultOpen?: boolean;
}

export function ThinkingBlock({ content, defaultOpen = false }: ThinkingBlockProps) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <motion.div
      initial={{ opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22 }}
      className="rounded-xl overflow-hidden"
      style={{
        background: "var(--bg-subtle)",
        border: "1px solid var(--border)",
      }}
    >
      <button
        onClick={() => setOpen((v) => !v)}
        className="w-full flex items-center gap-2 px-3 py-2 text-left transition hover:bg-black/[0.025]"
      >
        <BrainCircuit
          className="h-3.5 w-3.5 flex-shrink-0"
          style={{ color: "var(--ink-400)" }}
        />
        <span
          style={{
            fontSize: 11.5,
            fontWeight: 700,
            letterSpacing: "0.06em",
            color: "var(--ink-400)",
            textTransform: "uppercase",
            flex: 1,
          }}
        >
          Thinking
        </span>
        <motion.span
          animate={{ rotate: open ? 90 : 0 }}
          transition={{ duration: 0.16 }}
          style={{ display: "inline-flex" }}
        >
          <ChevronRight className="h-3 w-3" style={{ color: "var(--ink-300)" }} />
        </motion.span>
      </button>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22, ease: [0.4, 0, 0.2, 1] }}
            style={{ overflow: "hidden" }}
          >
            <div
              className="px-3 pb-3"
              style={{
                color: "var(--ink-500)",
                fontSize: 12.5,
                lineHeight: 1.7,
                borderTop: "1px solid var(--border)",
                paddingTop: 8,
              }}
            >
              {content}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────
// GlowPulse — brand-colored breathing dot for loading state
// ─────────────────────────────────────────────────────────────────
function GlowPulse() {
  return (
    <span
      className="relative inline-flex items-center justify-center flex-shrink-0"
      style={{ width: 12, height: 12 }}
    >
      <span
        className="absolute inset-0 rounded-full animate-ping"
        style={{
          background: "var(--brand)",
          opacity: 0.35,
          animationDuration: "1.6s",
        }}
      />
      <span
        className="relative rounded-full"
        style={{
          width: 7,
          height: 7,
          background: "var(--brand)",
          boxShadow: "0 0 6px 2px var(--brand-soft)",
        }}
      />
    </span>
  );
}

// ─────────────────────────────────────────────────────────────────
// StepConnector — vertical line between steps
// ─────────────────────────────────────────────────────────────────
function StepConnector({ lit }: { lit: boolean }) {
  return (
    <div
      className="w-[1.5px] mx-auto flex-1"
      style={{
        background: lit ? "var(--brand)" : "var(--border)",
        minHeight: 20,
        transition: "background 0.5s ease",
      }}
    />
  );
}

// ─────────────────────────────────────────────────────────────────
// StepNode — circle icon for each step
// ─────────────────────────────────────────────────────────────────
type NodeState = "idle" | "loading" | "done";

function StepNode({ state }: { state: NodeState }) {
  return (
    <motion.div
      className="flex items-center justify-center flex-shrink-0"
      style={{ width: 28, height: 28 }}
      layout
    >
      <AnimatePresence mode="wait">
        {state === "done" && (
          <motion.span
            key="done"
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.5, opacity: 0 }}
            transition={{ duration: 0.25, type: "spring", stiffness: 280, damping: 20 }}
          >
            <CheckCircle2 className="h-5 w-5" style={{ color: "#16a34a" }} />
          </motion.span>
        )}
        {state === "loading" && (
          <motion.div
            key="loading"
            initial={{ scale: 0.8, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.8, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="rounded-full flex items-center justify-center"
            style={{
              width: 26,
              height: 26,
              background: "var(--brand-soft)",
              border: "1px solid var(--brand-border)",
            }}
          >
            <Loader2 className="h-3.5 w-3.5 animate-spin" style={{ color: "var(--brand)" }} />
          </motion.div>
        )}
        {state === "idle" && (
          <motion.span
            key="idle"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <Circle className="h-5 w-5" style={{ color: "var(--ink-200)" }} />
          </motion.span>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────
// StepItem — one row in the stepper (icon rail + content)
// ─────────────────────────────────────────────────────────────────
interface StepItemProps {
  nodeState: NodeState;
  title: React.ReactNode;
  showConnector?: boolean;
  connectorLit?: boolean;
  children?: React.ReactNode;
}

export function StepItem({
  nodeState,
  title,
  showConnector = false,
  connectorLit = false,
  children,
}: StepItemProps) {
  return (
    <div className="flex gap-3">
      {/* Left rail: node + connector */}
      <div className="flex flex-col items-center" style={{ width: 28, flexShrink: 0 }}>
        <StepNode state={nodeState} />
        {showConnector && <StepConnector lit={connectorLit} />}
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0" style={{ paddingBottom: showConnector ? 20 : 0 }}>
        {/* Title row */}
        <div style={{ minHeight: 28, display: "flex", alignItems: "center" }}>
          <span
            style={{
              fontWeight: 650,
              fontSize: 14.5,
              color: nodeState === "done" ? "var(--ink-500)" : "var(--ink-900)",
              transition: "color 0.3s",
            }}
          >
            {title}
          </span>
        </div>

        {/* Expandable child content */}
        <AnimatePresence initial={false}>
          {children && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3, ease: [0.4, 0, 0.2, 1] }}
              style={{ overflow: "hidden" }}
            >
              <div className="mt-3 space-y-3">{children}</div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────────
// PlanStep — single checklist item with slide-in + optional typewriter
// ─────────────────────────────────────────────────────────────────
function PlanStep({ text, index, isNew = false }: { text: string; index: number; isNew?: boolean }) {
  return (
    <motion.div
      initial={{ opacity: 0, x: -10 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.22, ease: [0.34, 1.1, 0.64, 1] }}
      className="flex items-start gap-2.5"
      style={{ fontSize: 13.5, lineHeight: 1.65, color: "var(--ink-700)" }}
    >
      <span
        style={{
          color: "var(--ink-400)",
          fontVariantNumeric: "tabular-nums",
          minWidth: 20,
          fontWeight: 600,
          flexShrink: 0,
          paddingTop: 2,
          fontSize: 12.5,
        }}
      >
        {index + 1}.
      </span>
      <span className="flex-shrink-0" style={{ paddingTop: 4 }}>
        <span
          style={{
            width: 13,
            height: 13,
            border: "1.5px solid var(--ink-300)",
            borderRadius: 3,
            display: "inline-block",
          }}
        />
      </span>
      <span className="flex-1">
        {isNew ? <TypingText text={text} speed={12} /> : text}
      </span>
    </motion.div>
  );
}

// ─────────────────────────────────────────────────────────────────
// PlanStepper — main export
// ─────────────────────────────────────────────────────────────────
export interface PlanData {
  steps: string[];
  summary?: string;
  reasoning?: string;
  should_ask?: boolean;
}

export interface PlanStepperProps {
  planLoading: boolean;
  plan: PlanData | null;
  planError?: string | null;
  revealedPlanCount: number;
}

const INTRO_ASK =
  "模型判断这篇文档在执行前还需要确认几个关键点。确认后，我会开始执行，并在右侧实时写入文档草稿。";
const INTRO_GO =
  "模型判断当前信息已经足够，可以按下面计划直接开始执行，并在右侧实时写入文档草稿。";
const INTRO_LOADING =
  "我正在调用所选大模型理解你的需求，判断是否需要先追问，并生成这篇文档的专属执行计划。";

export function PlanStepper({
  planLoading,
  plan,
  planError,
  revealedPlanCount,
}: PlanStepperProps) {
  const allRevealed = plan ? revealedPlanCount >= plan.steps.length : false;
  const isDone = !planLoading && !!plan && allRevealed;
  const isStreaming = !!plan && !isDone;

  // introDone gates the ThinkingBlock + plan steps appearance
  const [introDone, setIntroDone] = useState(isDone);

  // Reset introDone when plan first arrives
  useEffect(() => {
    if (plan && !isDone) setIntroDone(false);
    if (isDone) setIntroDone(true);
  }, [!!plan, isDone]); // eslint-disable-line react-hooks/exhaustive-deps

  const nodeState: NodeState = isDone ? "done" : planLoading || isStreaming ? "loading" : "idle";
  const introText = planLoading && !plan ? INTRO_LOADING : plan?.should_ask ? INTRO_ASK : INTRO_GO;

  return (
    <div>
      <StepItem
        nodeState={nodeState}
        showConnector={false}
        title={
          isDone ? "任务规划完成" : planLoading && !plan ? "正在启动任务规划" : "任务规划"
        }
      >
        {/* ── State 1: Loading glow ─────────────────────────── */}
        {planLoading && !plan && !planError && (
          <motion.div
            key="loading-glow"
            initial={{ opacity: 0, y: 4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="flex items-center gap-3 px-3 py-2.5 rounded-xl"
            style={{
              background: "var(--brand-soft)",
              border: "1px solid var(--brand-border)",
            }}
          >
            <GlowPulse />
            <span style={{ fontSize: 13, color: "var(--ink-500)", fontWeight: 500 }}>
              正在生成计划...
            </span>
          </motion.div>
        )}

        {/* ── Error ────────────────────────────────────────── */}
        {planError && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="rounded-xl p-3"
            style={{
              background: "rgba(254,242,242,.72)",
              border: "1px solid rgba(220,38,38,.22)",
              color: "#991b1b",
              fontSize: 13,
              lineHeight: 1.65,
            }}
          >
            {planError}
          </motion.div>
        )}

        {/* ── State 2+: Plan content ────────────────────────── */}
        {plan && (
          <motion.div
            key="plan-content"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.2 }}
            className="space-y-3"
          >
            {/* Intro — typewriter during streaming, instant when done */}
            <div
              style={{
                color: "var(--ink-700)",
                fontSize: 13.5,
                lineHeight: 1.75,
              }}
            >
              <TypingText
                text={introText}
                speed={14}
                instant={isDone}
                onDone={() => setIntroDone(true)}
              />
            </div>

            {/* Thinking block — shows after intro types out */}
            <AnimatePresence>
              {(introDone || isDone) && plan.reasoning && (
                <ThinkingBlock content={plan.reasoning} defaultOpen={false} />
              )}
            </AnimatePresence>

            {/* Plan summary */}
            {(introDone || isDone) && plan.summary && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                style={{ color: "var(--ink-600)", fontSize: 13, lineHeight: 1.65 }}
              >
                {plan.summary}
              </motion.div>
            )}

            {/* Plan steps — stream in one by one */}
            {(introDone || isDone) && (
              <div className="space-y-2 pt-1">
                {plan.steps.slice(0, revealedPlanCount).map((item, index) => (
                  <PlanStep
                    key={item + index}
                    text={stripPlanStepNumber(item)}
                    index={index}
                    isNew={!isDone && index === revealedPlanCount - 1}
                  />
                ))}
                {!allRevealed && (
                  <motion.div
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="flex items-center gap-1.5"
                    style={{ color: "var(--ink-400)", fontSize: 12 }}
                  >
                    <Loader2 className="h-3 w-3 animate-spin" />
                    <span>生成中...</span>
                  </motion.div>
                )}
              </div>
            )}

            {/* Done badge */}
            <AnimatePresence>
              {isDone && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ duration: 0.25, type: "spring", stiffness: 260, damping: 18 }}
                  className="flex items-center gap-2 pt-1"
                  style={{ color: "#16a34a", fontSize: 13 }}
                >
                  <CheckCircle2 className="h-4 w-4" />
                  <span style={{ fontWeight: 650 }}>Done</span>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </StepItem>
    </div>
  );
}
