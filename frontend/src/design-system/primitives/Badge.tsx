import React from 'react';
import { cn } from '../utils';

export type BadgeTone =
  | 'neutral'
  | 'brand'
  | 'supervisor'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info';

export type BadgeVariant = 'soft' | 'outline' | 'solid';

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  variant?: BadgeVariant;
  size?: 'xs' | 'sm' | 'md';
  /** 左侧彩色点 */
  dot?: boolean;
  /** dot 是否呼吸（运行中） */
  pulsing?: boolean;
  icon?: React.ReactNode;
}

const toneCls = {
  neutral: {
    soft: 'bg-sunken text-ink-2 border-transparent',
    outline: 'bg-transparent text-ink-2 border-line',
    solid: 'bg-ink-1 text-white border-ink-1',
  },
  brand: {
    soft: 'bg-brand-soft text-brand border-transparent',
    outline: 'bg-transparent text-brand border-brand/40',
    solid: 'bg-brand text-white border-brand',
  },
  supervisor: {
    soft: 'bg-supervisor-soft text-supervisor border-transparent',
    outline: 'bg-transparent text-supervisor border-supervisor/40',
    solid: 'bg-supervisor text-white border-supervisor',
  },
  success: {
    soft: 'bg-success-soft text-success border-transparent',
    outline: 'bg-transparent text-success border-success/40',
    solid: 'bg-success text-white border-success',
  },
  warning: {
    soft: 'bg-warning-soft text-warning border-transparent',
    outline: 'bg-transparent text-warning border-warning/40',
    solid: 'bg-warning text-white border-warning',
  },
  danger: {
    soft: 'bg-danger-soft text-danger border-transparent',
    outline: 'bg-transparent text-danger border-danger/40',
    solid: 'bg-danger text-white border-danger',
  },
  info: {
    soft: 'bg-info-soft text-info border-transparent',
    outline: 'bg-transparent text-info border-info/40',
    solid: 'bg-info text-white border-info',
  },
} as const;

const dotCls = {
  neutral: 'bg-ink-3',
  brand: 'bg-brand',
  supervisor: 'bg-supervisor',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-danger',
  info: 'bg-info',
} as const;

const sizeCls = {
  xs: 'text-[10px] px-1.5 py-0.5 rounded gap-1',
  sm: 'text-[11px] px-1.5 py-0.5 rounded gap-1',
  md: 'text-[12px] px-2 py-0.5 rounded-md gap-1.5',
} as const;

export const Badge: React.FC<BadgeProps> = ({
  tone = 'neutral',
  variant = 'soft',
  size = 'sm',
  dot,
  pulsing,
  icon,
  className,
  children,
  ...rest
}) => {
  return (
    <span
      className={cn(
        'inline-flex items-center font-medium border whitespace-nowrap',
        toneCls[tone][variant],
        sizeCls[size],
        className,
      )}
      {...rest}
    >
      {dot && (
        <span
          className={cn(
            'inline-block h-1.5 w-1.5 rounded-full flex-shrink-0',
            dotCls[tone],
            pulsing && 'animate-pulse',
          )}
        />
      )}
      {icon && <span className="flex-shrink-0">{icon}</span>}
      {children}
    </span>
  );
};

export default Badge;
