import React, { useState, useRef, useEffect } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { AnimatePresence, motion } from 'framer-motion';
import { cn } from '../utils';

export interface SelectOption<V extends string | number = string> {
  value: V;
  label: React.ReactNode;
  description?: string;
  disabled?: boolean;
}

export interface SelectProps<V extends string | number = string> {
  value: V | undefined;
  onChange: (value: V) => void;
  options: SelectOption<V>[];
  placeholder?: string;
  disabled?: boolean;
  invalid?: boolean;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  /** 触发器左侧图标 */
  leftIcon?: React.ReactNode;
  /** 触发器前缀文案（如 "报告类型:"） */
  prefix?: React.ReactNode;
}

const sizeCls = {
  sm: 'h-8 text-[12.5px] px-2.5',
  md: 'h-10 text-[13.5px] px-3',
  lg: 'h-12 text-[15px] px-3.5',
} as const;

/**
 * Select primitive v3 —— 轻量自定义下拉（非原生 <select>）
 * - Popover 展开，键盘友好（Esc 关闭、Enter 选择）
 * - 可带前缀文案 → 支持 Compose Zone 的 "报告类型: 研究报告 ⌄" 形态
 */
export function Select<V extends string | number = string>({
  value,
  onChange,
  options,
  placeholder = '请选择',
  disabled,
  invalid,
  size = 'md',
  className,
  leftIcon,
  prefix,
}: SelectProps<V>) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDocClick);
    document.addEventListener('keydown', onEsc);
    return () => {
      document.removeEventListener('mousedown', onDocClick);
      document.removeEventListener('keydown', onEsc);
    };
  }, [open]);

  const current = options.find((o) => o.value === value);

  return (
    <div ref={rootRef} className={cn('relative inline-block', className)}>
      <button
        type="button"
        disabled={disabled}
        onClick={() => !disabled && setOpen((v) => !v)}
        className={cn(
          'inline-flex items-center gap-1.5 w-full text-left',
          'bg-surface border rounded-md text-ink-1',
          'transition-colors duration-base',
          'hover:border-line-strong',
          open && 'border-brand shadow-ring-brand',
          invalid
            ? 'border-danger'
            : open
              ? 'border-brand'
              : 'border-line',
          disabled && 'opacity-55 cursor-not-allowed hover:border-line',
          sizeCls[size],
        )}
      >
        {leftIcon && (
          <span className="flex-shrink-0 text-ink-3">{leftIcon}</span>
        )}
        {prefix && (
          <span className="flex-shrink-0 text-ink-3">{prefix}</span>
        )}
        <span
          className={cn(
            'flex-1 truncate',
            !current && 'text-ink-4',
          )}
        >
          {current ? current.label : placeholder}
        </span>
        <ChevronDown
          size={14}
          className={cn(
            'flex-shrink-0 text-ink-3 transition-transform duration-base',
            open && 'rotate-180',
          )}
        />
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.18, ease: [0.2, 0, 0, 1] }}
            className="absolute left-0 right-0 top-full mt-1 z-50 py-1 rounded-lg border border-line bg-elevated shadow-pop max-h-72 overflow-auto"
          >
            {options.map((opt) => {
              const selected = opt.value === value;
              return (
                <button
                  key={String(opt.value)}
                  type="button"
                  disabled={opt.disabled}
                  onClick={() => {
                    if (opt.disabled) return;
                    onChange(opt.value);
                    setOpen(false);
                  }}
                  className={cn(
                    'w-full flex items-start gap-2 px-2.5 py-2 text-left text-[13px]',
                    'transition-colors duration-fast',
                    'hover:bg-sunken',
                    selected && 'bg-brand-soft/50',
                    opt.disabled && 'opacity-50 cursor-not-allowed hover:bg-transparent',
                  )}
                >
                  <span className="flex-1 min-w-0">
                    <span className="block truncate text-ink-1">
                      {opt.label}
                    </span>
                    {opt.description && (
                      <span className="block mt-0.5 text-[11.5px] text-ink-3 truncate">
                        {opt.description}
                      </span>
                    )}
                  </span>
                  {selected && (
                    <Check size={14} className="flex-shrink-0 text-brand mt-0.5" />
                  )}
                </button>
              );
            })}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

export default Select;
