import React, { forwardRef } from 'react';
import { cn } from '../utils';

export interface TextareaProps
  extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  invalid?: boolean;
  autoResize?: boolean;
  minRows?: number;
  maxRows?: number;
}

/**
 * Textarea primitive v3
 * - autoResize：根据内容自动增高，常用于 Compose Zone 主输入框
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      className,
      invalid,
      autoResize,
      minRows = 3,
      maxRows = 12,
      onChange,
      rows,
      ...rest
    },
    forwardedRef,
  ) => {
    const innerRef = React.useRef<HTMLTextAreaElement | null>(null);

    // 合并外部 ref 和内部 ref
    const setRef = (node: HTMLTextAreaElement | null) => {
      innerRef.current = node;
      if (typeof forwardedRef === 'function') forwardedRef(node);
      else if (forwardedRef) forwardedRef.current = node;
    };

    const resize = React.useCallback(() => {
      const el = innerRef.current;
      if (!el || !autoResize) return;
      el.style.height = 'auto';
      const lineHeight = 22; // ~body line-height
      const minH = minRows * lineHeight + 16; // +padding
      const maxH = maxRows * lineHeight + 16;
      const next = Math.min(Math.max(el.scrollHeight, minH), maxH);
      el.style.height = `${next}px`;
      el.style.overflowY = el.scrollHeight > maxH ? 'auto' : 'hidden';
    }, [autoResize, minRows, maxRows]);

    React.useEffect(() => {
      if (autoResize) resize();
    }, [autoResize, resize, rest.value]);

    return (
      <textarea
        ref={setRef}
        rows={rows ?? minRows}
        onChange={(e) => {
          if (autoResize) resize();
          onChange?.(e);
        }}
        className={cn(
          'w-full bg-surface border rounded-md text-ink-1 px-3 py-2.5',
          'outline-none transition-colors duration-base resize-none',
          'placeholder:text-ink-4',
          'focus:border-brand focus:shadow-ring-brand',
          'disabled:bg-sunken disabled:text-ink-4 disabled:cursor-not-allowed',
          invalid
            ? 'border-danger focus:border-danger focus:shadow-[0_0_0_3px_rgba(220,38,38,0.18)]'
            : 'border-line',
          className,
        )}
        {...rest}
      />
    );
  },
);
Textarea.displayName = 'Textarea';

export default Textarea;
