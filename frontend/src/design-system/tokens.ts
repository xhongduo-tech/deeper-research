/**
 * Design System v3 · Tokens
 *
 * 对应 /DESIGN.md §5。所有 token 都有 CSS 变量对应，在 globals.css 里定义。
 * 这里提供 TS 常量，用于：
 *   1. 运行时动态样式（framer-motion、style 属性、canvas 绘制）
 *   2. 内联样式需要用到的场景
 *
 * 规则：
 *   - 静态样式请优先使用 Tailwind class 或 ds-* utility class
 *   - 仅在无法用类表达时才引用本文件的常量
 */

export const color = {
  // Canvas / surfaces
  canvas: '#fafaf9',
  surface: '#ffffff',
  elevated: '#ffffff',
  sunken: '#f5f4f0',
  mist: '#ececea',

  // Ink (neutral)
  ink1: '#141414',
  ink2: '#4a4a46',
  ink3: '#8a877e',
  ink4: '#bcb8ac',
  inkInverse: '#ffffff',

  // Lines
  lineSubtle: '#efeeea',
  line: '#e5e4e0',
  lineStrong: '#c8c5bd',

  // Brand (深研褐)
  brand: '#8c4f3a',
  brandHover: '#79412f',
  brandPressed: '#653424',
  brandSoft: '#f4e3d9',
  brandRing: 'rgba(140, 79, 58, 0.18)',

  // Supervisor (Chief 专属金)
  supervisor: '#c08a3a',
  supervisorHover: '#a8762e',
  supervisorSoft: '#f7ecd6',
  supervisorRing: 'rgba(192, 138, 58, 0.22)',

  // Semantic
  success: '#16a34a',
  warning: '#d97706',
  danger: '#dc2626',
  info: '#0ea5e9',
} as const;

export const radius = {
  sm: 6,
  md: 10,
  lg: 14,
  xl: 20,
  full: 9999,
} as const;

export const shadow = {
  sm: '0 1px 2px rgba(0, 0, 0, 0.05)',
  card:
    '0 1px 2px rgba(0, 0, 0, 0.04), 0 8px 24px -12px rgba(0, 0, 0, 0.10)',
  pop:
    '0 4px 12px rgba(0, 0, 0, 0.06), 0 20px 40px -16px rgba(0, 0, 0, 0.16)',
} as const;

export const motion = {
  // durations (ms)
  fast: 120,
  base: 180,
  slow: 260,
  page: 400,

  // easings
  emphasize: 'cubic-bezier(0.2, 0, 0, 1)',
  soft: 'cubic-bezier(0.4, 0, 0.2, 1)',
  exit: 'cubic-bezier(0.4, 0, 1, 1)',
} as const;

export const fontSize = {
  caption: 11,
  small: 13,
  body: 14,
  lead: 15,
  h3: 15,
  h2: 18,
  h1: 22,
  display: 28,
} as const;

export const fontFamily = {
  sans:
    'Inter, -apple-system, BlinkMacSystemFont, "PingFang SC", "HarmonyOS Sans SC", "Microsoft YaHei", "Hiragino Sans GB", "Noto Sans CJK SC", sans-serif',
  mono:
    '"JetBrains Mono", "SF Mono", Menlo, Monaco, Consolas, "Courier New", monospace',
} as const;

export type ColorToken = keyof typeof color;
