import React from 'react';
import { Inbox, AlertTriangle, RefreshCw } from 'lucide-react';
import { cn } from '../utils';

export interface EmptyStateProps {
  /** Optional icon; defaults to an inbox. */
  icon?: React.ReactNode;
  /** Single-line headline. */
  title: string;
  /** Short supporting text. Keep it to one sentence. */
  description?: React.ReactNode;
  /** Optional CTA (usually a Button). */
  action?: React.ReactNode;
  /** Compact variant (half the vertical padding) — use inside cards/lists. */
  compact?: boolean;
  className?: string;
}

/**
 * EmptyState primitive — the shared "nothing here" visual across the app.
 *
 * Intentionally lean: no background, no border. Callers place it inside
 * whatever card/panel is appropriate.
 */
export const EmptyState: React.FC<EmptyStateProps> = ({
  icon,
  title,
  description,
  action,
  compact,
  className,
}) => (
  <div
    className={cn(
      'flex flex-col items-center justify-center text-center',
      compact ? 'py-8 gap-2' : 'py-14 gap-3',
      className,
    )}
  >
    <div
      className={cn(
        'flex items-center justify-center rounded-full bg-sunken text-ink-4',
        compact ? 'h-9 w-9' : 'h-12 w-12',
      )}
    >
      {icon ?? <Inbox size={compact ? 16 : 20} />}
    </div>
    <div className="space-y-1">
      <p className="text-[13.5px] font-medium text-ink-1">{title}</p>
      {description && (
        <p className="max-w-sm text-[12.5px] leading-relaxed text-ink-3">
          {description}
        </p>
      )}
    </div>
    {action && <div className="mt-1">{action}</div>}
  </div>
);

export interface ErrorStateProps {
  title?: string;
  description?: React.ReactNode;
  onRetry?: () => void;
  retrying?: boolean;
  compact?: boolean;
  className?: string;
}

/**
 * ErrorState — the shared "something broke" visual.
 * Includes an optional retry button that wires up to React Query's refetch.
 */
export const ErrorState: React.FC<ErrorStateProps> = ({
  title = '加载失败',
  description = '请稍后重试,或联系管理员检查后端服务。',
  onRetry,
  retrying,
  compact,
  className,
}) => (
  <div
    className={cn(
      'flex flex-col items-center justify-center text-center',
      compact ? 'py-8 gap-2' : 'py-14 gap-3',
      className,
    )}
  >
    <div
      className={cn(
        'flex items-center justify-center rounded-full bg-danger-soft text-danger',
        compact ? 'h-9 w-9' : 'h-12 w-12',
      )}
    >
      <AlertTriangle size={compact ? 16 : 20} />
    </div>
    <div className="space-y-1">
      <p className="text-[13.5px] font-medium text-ink-1">{title}</p>
      {description && (
        <p className="max-w-sm text-[12.5px] leading-relaxed text-ink-3">
          {description}
        </p>
      )}
    </div>
    {onRetry && (
      <button
        type="button"
        onClick={onRetry}
        disabled={retrying}
        className="inline-flex items-center gap-1.5 rounded-md border border-line px-3 py-1.5 text-[12.5px] text-ink-2 hover:border-ink-3 hover:text-ink-1 disabled:opacity-50"
      >
        <RefreshCw
          size={12}
          className={retrying ? 'animate-spin' : undefined}
        />
        重试
      </button>
    )}
  </div>
);

export interface LoadingStateProps {
  label?: string;
  compact?: boolean;
  className?: string;
}

/**
 * LoadingState — tiny centered spinner + label. Use for in-panel loading.
 * For full-page loading, use PageLoader instead.
 */
export const LoadingState: React.FC<LoadingStateProps> = ({
  label = '加载中…',
  compact,
  className,
}) => (
  <div
    className={cn(
      'flex items-center justify-center gap-2 text-ink-3',
      compact ? 'py-6' : 'py-12',
      className,
    )}
  >
    <RefreshCw size={14} className="animate-spin" />
    <span className="text-[12.5px]">{label}</span>
  </div>
);
