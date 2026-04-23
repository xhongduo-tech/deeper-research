import React from 'react';
import { motion } from 'framer-motion';
import { cn } from '../utils';

export interface TabItem<V extends string = string> {
  value: V;
  label: React.ReactNode;
  badge?: React.ReactNode;
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface TabsProps<V extends string = string> {
  value: V;
  onChange: (value: V) => void;
  items: TabItem<V>[];
  /** line: 下划线式 / pill: 胶囊式 */
  variant?: 'line' | 'pill';
  size?: 'sm' | 'md';
  className?: string;
}

/**
 * Tabs primitive v3
 * - line 变体：Linear 风下划线 tabs，含 motion 动画的滑动 indicator
 * - pill 变体：胶囊 tabs，适合放在紧凑工具栏
 */
export function Tabs<V extends string = string>({
  value,
  onChange,
  items,
  variant = 'line',
  size = 'md',
  className,
}: TabsProps<V>) {
  if (variant === 'pill') {
    return (
      <div
        className={cn(
          'inline-flex items-center gap-1 p-1 rounded-md bg-sunken',
          className,
        )}
      >
        {items.map((it) => {
          const active = it.value === value;
          return (
            <button
              key={it.value}
              type="button"
              disabled={it.disabled}
              onClick={() => !it.disabled && onChange(it.value)}
              className={cn(
                'relative inline-flex items-center gap-1.5 px-3 rounded-[6px]',
                'font-medium transition-colors duration-base',
                size === 'sm' ? 'h-7 text-[12.5px]' : 'h-8 text-[13px]',
                active
                  ? 'bg-surface text-ink-1 shadow-sm'
                  : 'text-ink-3 hover:text-ink-1',
                it.disabled && 'opacity-50 cursor-not-allowed',
              )}
            >
              {it.icon}
              {it.label}
              {it.badge}
            </button>
          );
        })}
      </div>
    );
  }

  // line variant
  return (
    <div
      className={cn(
        'flex items-end gap-1 border-b border-line-subtle',
        className,
      )}
    >
      {items.map((it) => {
        const active = it.value === value;
        return (
          <button
            key={it.value}
            type="button"
            disabled={it.disabled}
            onClick={() => !it.disabled && onChange(it.value)}
            className={cn(
              'relative inline-flex items-center gap-1.5 px-3',
              'font-medium transition-colors duration-base',
              size === 'sm' ? 'h-8 text-[12.5px]' : 'h-10 text-[13.5px]',
              active ? 'text-ink-1' : 'text-ink-3 hover:text-ink-1',
              it.disabled && 'opacity-50 cursor-not-allowed',
            )}
          >
            {it.icon}
            {it.label}
            {it.badge}
            {active && (
              <motion.span
                layoutId="tabs-indicator"
                className="absolute left-0 right-0 -bottom-px h-0.5 bg-ink-1"
                transition={{ duration: 0.18, ease: [0.2, 0, 0, 1] }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}

export default Tabs;
