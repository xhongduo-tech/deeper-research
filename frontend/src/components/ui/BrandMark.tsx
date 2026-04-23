import React from 'react';

interface BrandMarkProps {
  size?: number;
  /**
   * Retained for backwards compatibility. The refined LobeHub logo has its
   * own color palette so variants now only toggle background treatment.
   */
  variant?: 'gradient' | 'mono' | 'subtle';
  className?: string;
}

/**
 * dataagent brand mark — the refined LobeHub logo: a magnifying-glass circling
 * a small bar-chart with a trend line, drawn in warm clay/terracotta tones.
 *
 * Rendered as inline SVG so color/size work in any browser without relying on
 * <img> loading. Kept compact (no gradients that old browsers may mis-render —
 * we keep the original gradients since radial/linear gradients work in IE11+).
 */
export const BrandMark: React.FC<BrandMarkProps> = ({
  size = 36,
  variant: _variant = 'gradient',
  className = '',
}) => {
  const uid = React.useId().replace(/:/g, '');
  const id = (k: string) => `bm-${uid}-${k}`;

  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 400 400"
      role="img"
      aria-label="dataagent · 深度研究数据分析智能体"
      className={className}
    >
      <defs>
        <linearGradient id={id('g1')} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#E8956D" />
          <stop offset="100%" stopColor="#C96442" />
        </linearGradient>
        <linearGradient id={id('g2')} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#D4785A" />
          <stop offset="100%" stopColor="#B85C38" />
        </linearGradient>
        <linearGradient id={id('g3')} x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stopColor="#F0A882" />
          <stop offset="100%" stopColor="#D4785A" />
        </linearGradient>
        <linearGradient id={id('bar')} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop offset="0%" stopColor="#E8956D" />
          <stop offset="100%" stopColor="#C96442" />
        </linearGradient>
        <radialGradient id={id('bg')} cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#FDF6F0" />
          <stop offset="100%" stopColor="#F5EBE0" />
        </radialGradient>
      </defs>

      <circle cx="200" cy="200" r="200" fill={`url(#${id('bg')})`} />

      {/* Magnifier ring */}
      <circle
        cx="185"
        cy="178"
        r="88"
        fill="none"
        stroke={`url(#${id('g1')})`}
        strokeWidth="22"
        strokeLinecap="round"
      />
      {/* Handle */}
      <line
        x1="249"
        y1="245"
        x2="306"
        y2="308"
        stroke={`url(#${id('g2')})`}
        strokeWidth="22"
        strokeLinecap="round"
      />

      {/* Bars */}
      <rect x="148" y="195" width="18" height="42" rx="5" fill={`url(#${id('bar')})`} opacity="0.9" />
      <rect x="176" y="172" width="18" height="65" rx="5" fill={`url(#${id('g2')})`} opacity="0.95" />
      <rect x="204" y="183" width="18" height="54" rx="5" fill={`url(#${id('g3')})`} opacity="0.9" />

      {/* Trend line */}
      <polyline
        points="148,195 185,168 222,178"
        fill="none"
        stroke="#C96442"
        strokeWidth="5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.85"
      />
      <circle cx="148" cy="195" r="5" fill="#C96442" opacity="0.9" />
      <circle cx="185" cy="168" r="5" fill="#C96442" opacity="0.9" />
      <circle cx="222" cy="178" r="5" fill="#C96442" opacity="0.9" />
    </svg>
  );
};

export default BrandMark;
