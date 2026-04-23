import React from 'react';

export type BadgeTone =
  | 'neutral'
  | 'brand'
  | 'cedar'
  | 'gold'
  | 'success'
  | 'warning'
  | 'danger'
  | 'info';

interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  variant?: 'solid' | 'soft' | 'outline';
  dot?: boolean;
  animatedDot?: boolean;
  size?: 'xs' | 'sm';
}

const toneMap: Record<
  BadgeTone,
  { solid: string; soft: string; outline: string; dot: string }
> = {
  neutral: {
    solid: 'bg-ink-2 text-ink-inverse',
    soft: 'bg-sunken text-ink-2 border border-line-subtle',
    outline: 'border border-line text-ink-2',
    dot: 'bg-ink-3',
  },
  brand: {
    solid: 'bg-brand text-ink-inverse',
    soft: 'bg-brand-soft text-brand border border-brand/25',
    outline: 'border border-brand/35 text-brand',
    dot: 'bg-brand',
  },
  cedar: {
    solid: 'bg-cedar text-ink-inverse',
    soft: 'bg-cedar-soft text-cedar border border-cedar/25',
    outline: 'border border-cedar/35 text-cedar',
    dot: 'bg-cedar',
  },
  gold: {
    solid: 'bg-gold text-ink-inverse',
    soft: 'bg-gold-soft text-gold border border-gold/30',
    outline: 'border border-gold/35 text-gold',
    dot: 'bg-gold',
  },
  success: {
    solid: 'bg-success text-ink-inverse',
    soft: 'bg-success-soft text-success border border-success/25',
    outline: 'border border-success/35 text-success',
    dot: 'bg-success',
  },
  warning: {
    solid: 'bg-warning text-ink-inverse',
    soft: 'bg-warning-soft text-warning border border-warning/25',
    outline: 'border border-warning/35 text-warning',
    dot: 'bg-warning',
  },
  danger: {
    solid: 'bg-danger text-ink-inverse',
    soft: 'bg-danger-soft text-danger border border-danger/25',
    outline: 'border border-danger/35 text-danger',
    dot: 'bg-danger',
  },
  info: {
    solid: 'bg-info text-ink-inverse',
    soft: 'bg-info-soft text-info border border-info/25',
    outline: 'border border-info/35 text-info',
    dot: 'bg-info',
  },
};

const sizeMap = {
  xs: 'text-[11px] leading-4 px-1.5 py-0 h-[18px]',
  sm: 'text-[12px] leading-[18px] px-2 py-0 h-5',
};

export const Badge: React.FC<BadgeProps> = ({
  tone = 'neutral',
  variant = 'soft',
  size = 'sm',
  dot,
  animatedDot,
  className = '',
  children,
  ...rest
}) => {
  const styles = toneMap[tone][variant];
  return (
    <span
      className={[
        'inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap',
        sizeMap[size],
        styles,
        className,
      ]
        .filter(Boolean)
        .join(' ')}
      {...rest}
    >
      {dot && (
        <span
          className={[
            'h-1.5 w-1.5 flex-shrink-0 rounded-full',
            toneMap[tone].dot,
            animatedDot ? 'animate-pulse' : '',
          ]
            .filter(Boolean)
            .join(' ')}
        />
      )}
      {children}
    </span>
  );
};

export default Badge;
