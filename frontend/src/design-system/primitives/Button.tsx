import React, { forwardRef } from 'react';
import { Loader2 } from 'lucide-react';
import { cn } from '../utils';

export type ButtonVariant =
  | 'primary' // 深研褐，主 CTA
  | 'secondary' // 黑色，次级 CTA (Vercel 风)
  | 'outline' // 边框，tertiary
  | 'ghost' // 无边框无背景
  | 'danger' // 红色危险操作
  | 'supervisor'; // 金色，Chief 相关动作（仅协作室使用）

export type ButtonSize = 'xs' | 'sm' | 'md' | 'lg';

export interface ButtonProps
  extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'disabled'> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
  disabled?: boolean;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  fullWidth?: boolean;
}

const variantCls: Record<ButtonVariant, string> = {
  primary:
    'bg-brand text-ink-inverse border-brand hover:bg-brand-hover hover:border-brand-hover active:bg-brand-pressed',
  secondary:
    'bg-[#141414] text-white border-[#141414] hover:bg-[#2a2a2a] hover:border-[#2a2a2a] active:bg-black',
  outline:
    'bg-transparent text-ink-2 border-line hover:bg-sunken hover:border-line-strong hover:text-ink-1',
  ghost:
    'bg-transparent text-ink-2 border-transparent hover:bg-sunken hover:text-ink-1',
  danger:
    'bg-transparent text-danger border-danger/35 hover:bg-danger/8 hover:border-danger',
  supervisor:
    'bg-supervisor text-white border-supervisor hover:bg-supervisor-hover hover:border-supervisor-hover',
};

const sizeCls: Record<ButtonSize, string> = {
  xs: 'h-7 px-2.5 text-[12px] gap-1 rounded-md',
  sm: 'h-8 px-3 text-[12.5px] gap-1.5 rounded-md',
  md: 'h-10 px-4 text-[13.5px] gap-1.5 rounded-md',
  lg: 'h-12 px-5 text-[15px] gap-2 rounded-lg',
};

/**
 * Button primitive v3 — 见 DESIGN.md §5
 *
 * 核心差异 vs 旧 ui/Button：
 *   - secondary 改为 Vercel 风黑色（原 cedar 绿被 legacy 化）
 *   - 新增 `supervisor` variant（Chief 专属金色）
 *   - 新增 `xs` size
 *   - 所有动效 token 化（transition-base / 180ms / emphasize）
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = 'primary',
      size = 'md',
      loading,
      disabled,
      leftIcon,
      rightIcon,
      fullWidth,
      children,
      className,
      type = 'button',
      ...rest
    },
    ref,
  ) => {
    const iconSize = size === 'lg' ? 16 : size === 'xs' ? 12 : 14;
    return (
      <button
        ref={ref}
        type={type}
        disabled={disabled || loading}
        className={cn(
          'inline-flex items-center justify-center whitespace-nowrap font-medium border',
          'transition-colors duration-base ease-[cubic-bezier(0.2,0,0,1)]',
          'focus-visible:outline-none focus-visible:shadow-ring-brand',
          'active:scale-[0.98] transition-transform',
          'disabled:opacity-55 disabled:cursor-not-allowed',
          variantCls[variant],
          sizeCls[size],
          fullWidth && 'w-full',
          className,
        )}
        {...rest}
      >
        {loading ? (
          <Loader2 size={iconSize} className="animate-spin" />
        ) : (
          leftIcon && <span className="flex-shrink-0">{leftIcon}</span>
        )}
        {children && <span>{children}</span>}
        {!loading && rightIcon && (
          <span className="flex-shrink-0">{rightIcon}</span>
        )}
      </button>
    );
  },
);
Button.displayName = 'Button';

export default Button;
