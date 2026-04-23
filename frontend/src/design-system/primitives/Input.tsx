import React, { forwardRef } from 'react';
import { cn } from '../utils';

export interface InputProps
  extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size'> {
  invalid?: boolean;
  leftIcon?: React.ReactNode;
  rightSlot?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}

const sizeCls = {
  sm: 'h-8 text-[12.5px] px-2.5',
  md: 'h-10 text-[13.5px] px-3',
  lg: 'h-12 text-[15px] px-3.5',
} as const;

/**
 * Input primitive v3
 * - 白底 / 浅灰边 / 焦点态 brand ring
 * - 支持左图标和右侧 slot（常用于 clear 按钮、unit label）
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(
  (
    { className, invalid, leftIcon, rightSlot, size = 'md', ...rest },
    ref,
  ) => {
    if (leftIcon || rightSlot) {
      return (
        <div
          className={cn(
            'flex items-center border rounded-md bg-surface',
            'transition-colors duration-base',
            'focus-within:border-brand focus-within:shadow-ring-brand',
            invalid
              ? 'border-danger focus-within:border-danger focus-within:shadow-[0_0_0_3px_rgba(220,38,38,0.18)]'
              : 'border-line',
            sizeCls[size],
            'px-0',
            className,
          )}
        >
          {leftIcon && (
            <span className="pl-3 pr-1.5 text-ink-3 flex-shrink-0">
              {leftIcon}
            </span>
          )}
          <input
            ref={ref}
            className={cn(
              'flex-1 bg-transparent outline-none border-0 px-3 text-ink-1',
              'placeholder:text-ink-4',
              leftIcon && 'pl-0',
            )}
            {...rest}
          />
          {rightSlot && (
            <span className="pr-2 flex-shrink-0">{rightSlot}</span>
          )}
        </div>
      );
    }
    return (
      <input
        ref={ref}
        className={cn(
          'w-full bg-surface border rounded-md text-ink-1',
          'outline-none transition-colors duration-base',
          'placeholder:text-ink-4',
          'focus:border-brand focus:shadow-ring-brand',
          'disabled:bg-sunken disabled:text-ink-4 disabled:cursor-not-allowed',
          invalid
            ? 'border-danger focus:border-danger focus:shadow-[0_0_0_3px_rgba(220,38,38,0.18)]'
            : 'border-line',
          sizeCls[size],
          className,
        )}
        {...rest}
      />
    );
  },
);
Input.displayName = 'Input';

export default Input;
