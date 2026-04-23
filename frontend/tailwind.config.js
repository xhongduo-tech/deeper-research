/** @type {import('tailwindcss').Config} */
export default {
  content: [
    './index.html',
    './src/**/*.{js,ts,jsx,tsx}',
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        /* -----------------------------------------------------------
         *  Design System v3 — Vercel/Linear 风中性 + 深研褐强调
         *  见 /DESIGN.md §5
         *  Legacy aliases (bg.*, text.*, border, accent.*, status.*)
         *  映射到新色值，旧 JSX 无需修改自动跟随视觉升级
         * ----------------------------------------------------------- */

        // Canvas / surfaces — use CSS vars so dark mode propagates
        canvas:   'rgb(var(--c-canvas)   / <alpha-value>)',
        surface:  'rgb(var(--c-surface)  / <alpha-value>)',
        elevated: 'rgb(var(--c-elevated) / <alpha-value>)',
        sunken:   'rgb(var(--c-sunken)   / <alpha-value>)',
        mist:     'rgb(var(--c-mist)     / <alpha-value>)',
        veil: 'rgba(20, 20, 20, 0.42)',

        // Ink — pure neutral (alpha-value enables bg-ink-1/[0.06] etc.)
        ink: {
          DEFAULT: 'rgb(var(--c-ink-1)   / <alpha-value>)',
          1:       'rgb(var(--c-ink-1)   / <alpha-value>)',
          2:       'rgb(var(--c-ink-2)   / <alpha-value>)',
          3:       'rgb(var(--c-ink-3)   / <alpha-value>)',
          4:       'rgb(var(--c-ink-4)   / <alpha-value>)',
          inverse: 'rgb(var(--c-ink-inv) / <alpha-value>)',
        },

        // Lines
        line: {
          subtle:  'rgb(var(--c-line-sub) / <alpha-value>)',
          DEFAULT: 'rgb(var(--c-line)     / <alpha-value>)',
          strong:  'rgb(var(--c-line-str) / <alpha-value>)',
        },

        // Brand（深研褐）
        brand: {
          DEFAULT: 'rgb(var(--c-brand) / <alpha-value>)',
          hover:   '#79412f',
          pressed: '#653424',
          soft:    'var(--color-brand-soft)',
          ring:    'var(--color-brand-ring)',
        },

        // Supervisor 金（Chief 专属）
        supervisor: {
          DEFAULT: 'rgb(var(--c-supervisor) / <alpha-value>)',
          hover:   '#a8762e',
          soft:    'var(--color-supervisor-soft)',
          ring:    'var(--color-supervisor-ring)',
        },

        // Legacy cedar/gold（保留兜底，不推荐新代码使用）
        cedar: {
          DEFAULT: '#6b7a4f',
          hover: '#5a6841',
          soft: '#e7ead9',
          ring: 'rgba(107, 122, 79, 0.28)',
        },
        gold: {
          DEFAULT: '#a27b36',
          soft: '#f4e6c8',
        },

        // Semantic — 仅 4 色
        success: { DEFAULT: '#16a34a', soft: '#dcfce7' },
        warning: { DEFAULT: '#d97706', soft: '#fef3c7' },
        danger:  { DEFAULT: '#dc2626', soft: '#fee2e2' },
        info:    { DEFAULT: '#0ea5e9', soft: '#e0f2fe' },

        /* ---------- Legacy aliases ---------- */
        bg: {
          primary:   'rgb(var(--c-canvas)  / <alpha-value>)',
          secondary: 'rgb(var(--c-surface) / <alpha-value>)',
          card:      'rgb(var(--c-surface) / <alpha-value>)',
        },
        text: {
          primary:   'rgb(var(--c-ink-1) / <alpha-value>)',
          secondary: 'rgb(var(--c-ink-2) / <alpha-value>)',
          muted:     'rgb(var(--c-ink-3) / <alpha-value>)',
        },
        border: {
          DEFAULT: 'rgb(var(--c-line)     / <alpha-value>)',
          light:   'rgb(var(--c-line-str) / <alpha-value>)',
        },
        accent: {
          red: '#8c4f3a',
          teal: '#6b7a4f',
          gold: '#a27b36',
        },
        status: {
          success: '#16a34a',
          warning: '#d97706',
          error: '#dc2626',
          info: '#0ea5e9',
        },
      },

      fontFamily: {
        sans: [
          '"Inter"',
          '-apple-system',
          'BlinkMacSystemFont',
          '"PingFang SC"',
          '"HarmonyOS Sans SC"',
          '"Microsoft YaHei"',
          '"Hiragino Sans GB"',
          '"Noto Sans CJK SC"',
          'sans-serif',
        ],
        serif: [
          '"Noto Serif SC"',
          '"Songti SC"',
          '"STSong"',
          'ui-serif',
          'Georgia',
          'serif',
        ],
        mono: [
          '"JetBrains Mono"',
          '"SF Mono"',
          'Menlo',
          'Monaco',
          'Consolas',
          '"Courier New"',
          'monospace',
        ],
      },

      fontSize: {
        // name: [size, { lineHeight, letterSpacing }]
        caption: ['11px', { lineHeight: '16px', letterSpacing: '0.02em' }],
        small:   ['12.5px', { lineHeight: '18px' }],
        body:    ['14px', { lineHeight: '22px' }],
        lead:    ['15px', { lineHeight: '24px' }],
        h5:      ['15px',  { lineHeight: '22px', letterSpacing: '-0.005em' }],
        h4:      ['16px',  { lineHeight: '24px', letterSpacing: '-0.005em' }],
        h3:      ['18px',  { lineHeight: '26px', letterSpacing: '-0.005em' }],
        h2:      ['22px',  { lineHeight: '30px', letterSpacing: '-0.01em' }],
        h1:      ['28px',  { lineHeight: '36px', letterSpacing: '-0.015em' }],
        display: ['36px',  { lineHeight: '44px', letterSpacing: '-0.02em' }],
      },

      borderRadius: {
        none: '0',
        xs: '4px',
        sm: '6px',
        DEFAULT: '10px',
        md: '10px',
        lg: '14px',
        xl: '20px',
        '2xl': '28px',
        full: '9999px',
      },

      boxShadow: {
        'xs':      '0 1px 2px rgba(0, 0, 0, 0.04)',
        'sm':      '0 1px 2px rgba(0, 0, 0, 0.05)',
        'card':    '0 1px 2px rgba(0, 0, 0, 0.04), 0 8px 24px -12px rgba(0, 0, 0, 0.10)',
        'card-hover': '0 1px 3px rgba(0, 0, 0, 0.05), 0 12px 28px -14px rgba(0, 0, 0, 0.14)',
        'pop':     '0 4px 12px rgba(0, 0, 0, 0.06), 0 20px 40px -16px rgba(0, 0, 0, 0.16)',
        'ring-brand':      '0 0 0 3px rgba(140, 79, 58, 0.18)',
        'ring-supervisor': '0 0 0 3px rgba(192, 138, 58, 0.22)',
        'glow-brand':      '0 0 0 6px rgba(140, 79, 58, 0.10)',
        'glow-supervisor': '0 0 0 6px rgba(192, 138, 58, 0.14)',
      },

      spacing: {
        '2.5': '10px',
        '4.5': '18px',
        '5.5': '22px',
        '18':  '72px',
      },

      transitionTimingFunction: {
        'emphasize': 'cubic-bezier(0.2, 0, 0, 1)',
        'soft': 'cubic-bezier(0.4, 0, 0.2, 1)',
      },

      animation: {
        /* 基础动效（见 DESIGN.md §5） */
        'fade-in':     'fadeIn 180ms cubic-bezier(0.2, 0, 0, 1)',
        'fade-out':    'fadeOut 120ms cubic-bezier(0.4, 0, 1, 1)',
        'slide-up':    'slideUp 180ms cubic-bezier(0.2, 0, 0, 1)',
        'slide-in-left': 'slideInLeft 260ms cubic-bezier(0.2, 0, 0, 1)',
        /* 协作室专用 */
        'msg-in':      'msgIn 220ms cubic-bezier(0.2, 0, 0, 1)',
        'msg-flash':   'msgFlash 600ms ease-out',
        /* 章节增量亮起 */
        'section-reveal': 'sectionReveal 320ms cubic-bezier(0.2, 0, 0, 1)',
        /* 骨架 / 思考 / pulse */
        'thinking':    'thinking 1.4s ease-in-out infinite',
        'shimmer':     'shimmer 1.4s linear infinite',
        'pulse-ring':  'pulseRing 2.4s ease-in-out infinite',
        'pulse-ring-supervisor': 'pulseRingSupervisor 2.4s ease-in-out infinite',
      },

      keyframes: {
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
        fadeOut: {
          '0%':   { opacity: '1' },
          '100%': { opacity: '0' },
        },
        slideUp: {
          '0%':   { opacity: '0', transform: 'translateY(6px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideInLeft: {
          '0%':   { opacity: '0', transform: 'translateX(-12px)' },
          '100%': { opacity: '1', transform: 'translateX(0)' },
        },
        msgIn: {
          '0%':   { opacity: '0', transform: 'translateY(8px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        msgFlash: {
          '0%':   { backgroundColor: 'rgba(140, 79, 58, 0)' },
          '30%':  { backgroundColor: 'rgba(140, 79, 58, 0.08)' },
          '100%': { backgroundColor: 'rgba(140, 79, 58, 0)' },
        },
        sectionReveal: {
          '0%':   { opacity: '0.3', transform: 'translateY(4px)' },
          '100%': { opacity: '1',   transform: 'translateY(0)' },
        },
        thinking: {
          '0%, 100%': { opacity: '0.3', transform: 'translateY(0)' },
          '50%':      { opacity: '1',   transform: 'translateY(-2px)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0', opacity: '0.4' },
          '50%':  { opacity: '0.7' },
          '100%': { backgroundPosition: '200% 0',  opacity: '0.4' },
        },
        pulseRing: {
          '0%':   { boxShadow: '0 0 0 0 rgba(140, 79, 58, 0.24)' },
          '70%':  { boxShadow: '0 0 0 10px rgba(140, 79, 58, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(140, 79, 58, 0)' },
        },
        pulseRingSupervisor: {
          '0%':   { boxShadow: '0 0 0 0 rgba(192, 138, 58, 0.28)' },
          '70%':  { boxShadow: '0 0 0 10px rgba(192, 138, 58, 0)' },
          '100%': { boxShadow: '0 0 0 0 rgba(192, 138, 58, 0)' },
        },
      },

      backgroundImage: {
        /* v3 去掉纸纹背景，保留 token 避免引用报错 */
        'paper-grain': 'none',
      },

      transitionDuration: {
        'fast': '120ms',
        'base': '180ms',
        'slow': '260ms',
        'page': '400ms',
      },
    },
  },
  plugins: [],
};
