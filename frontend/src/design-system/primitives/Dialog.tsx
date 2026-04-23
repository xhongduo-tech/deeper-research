import React, { useEffect } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { X } from 'lucide-react';
import { cn } from '../utils';

export interface DialogProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  children?: React.ReactNode;
  footer?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  /** 是否显示右上角 × */
  closable?: boolean;
  /** 点击遮罩是否关闭 */
  dismissOnBackdrop?: boolean;
  className?: string;
}

const widthCls = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-2xl',
} as const;

/**
 * Dialog primitive v3 —— 模态对话框
 *
 * 关键：
 *   - 遮罩 fade，内容 slide-up
 *   - Esc 关闭、点遮罩关闭（可配置）
 *   - 使用 React portal 挂到 body 末尾避免 z-index 问题（简化版：依赖 fixed 布局）
 */
export const Dialog: React.FC<DialogProps> = ({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = 'md',
  closable = true,
  dismissOnBackdrop = true,
  className,
}) => {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    // lock scroll
    const prev = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    return () => {
      document.removeEventListener('keydown', onKey);
      document.body.style.overflow = prev;
    };
  }, [open, onClose]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[90] flex items-center justify-center p-4">
          {/* 遮罩 */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            onClick={dismissOnBackdrop ? onClose : undefined}
            className="absolute inset-0 bg-[rgba(20,20,20,0.42)] backdrop-blur-[2px]"
          />
          {/* 内容 */}
          <motion.div
            initial={{ opacity: 0, y: 8, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 8, scale: 0.98 }}
            transition={{ duration: 0.18, ease: [0.2, 0, 0, 1] }}
            className={cn(
              'relative z-10 w-full rounded-xl bg-elevated shadow-pop border border-line-subtle',
              widthCls[size],
              className,
            )}
          >
            {(title || closable) && (
              <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-3">
                <div className="min-w-0 flex-1">
                  {title && (
                    <h3 className="text-[16px] font-semibold leading-snug text-ink-1">
                      {title}
                    </h3>
                  )}
                  {description && (
                    <p className="mt-1 text-[13px] text-ink-3">
                      {description}
                    </p>
                  )}
                </div>
                {closable && (
                  <button
                    type="button"
                    onClick={onClose}
                    className="flex-shrink-0 text-ink-3 hover:text-ink-1 transition-colors p-1 -m-1 rounded-sm"
                    aria-label="关闭"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            )}
            {children && (
              <div className="px-5 pb-4 text-[13.5px] text-ink-2">
                {children}
              </div>
            )}
            {footer && (
              <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-line-subtle bg-sunken/30 rounded-b-xl">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default Dialog;
