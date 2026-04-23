import React from 'react';
import { cn } from '../utils';

export interface ProgressRingProps {
  /** 0-1 */
  value: number;
  size?: number;
  thickness?: number;
  /** track 颜色 */
  trackColor?: string;
  /** 填充颜色（默认 brand） */
  color?: string;
  /** 中间显示内容（默认显示百分比） */
  label?: React.ReactNode;
  /** 是否呼吸动画（运行中） */
  active?: boolean;
  className?: string;
}

/**
 * ProgressRing primitive v3 —— 报告生产态的核心视觉
 *
 * 用于 /reports/:id 主区的大进度环
 * - 规格：默认 size=128，thickness=6
 * - 数字从小滑动到大（动画由外部 value 变化自然驱动）
 */
export const ProgressRing: React.FC<ProgressRingProps> = ({
  value,
  size = 128,
  thickness = 6,
  trackColor = '#ececea',
  color = '#8c4f3a',
  label,
  active,
  className,
}) => {
  const clamped = Math.max(0, Math.min(1, value));
  const r = (size - thickness) / 2;
  const c = 2 * Math.PI * r;
  const offset = c * (1 - clamped);
  const pct = Math.round(clamped * 100);

  return (
    <div
      className={cn('relative inline-flex items-center justify-center', className)}
      style={{ width: size, height: size }}
    >
      <svg
        width={size}
        height={size}
        viewBox={`0 0 ${size} ${size}`}
        className={cn(active && 'animate-pulse')}
        style={{ animationDuration: '2.4s' }}
      >
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={trackColor}
          strokeWidth={thickness}
          fill="none"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={thickness}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
          style={{
            transition: 'stroke-dashoffset 400ms cubic-bezier(0.2, 0, 0, 1)',
          }}
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        {label ?? (
          <span className="font-semibold tabular-nums text-ink-1" style={{ fontSize: size * 0.22 }}>
            {pct}
            <span className="ml-0.5 text-ink-3" style={{ fontSize: size * 0.14 }}>
              %
            </span>
          </span>
        )}
      </div>
    </div>
  );
};

export default ProgressRing;
