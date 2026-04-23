import React, { useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X } from 'lucide-react';

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title?: React.ReactNode;
  description?: React.ReactNode;
  children: React.ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  showCloseButton?: boolean;
  footer?: React.ReactNode;
}

const sizeClasses = {
  sm: 'max-w-sm',
  md: 'max-w-md',
  lg: 'max-w-lg',
  xl: 'max-w-2xl',
};

export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  description,
  children,
  size = 'md',
  showCloseButton = true,
  footer,
}) => {
  const modalRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && open) onClose();
    };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden';
    else document.body.style.overflow = '';
    return () => {
      document.body.style.overflow = '';
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 bg-veil backdrop-blur-sm"
            onClick={onClose}
          />

          <motion.div
            ref={modalRef}
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.22, ease: [0.2, 0, 0, 1] }}
            className={[
              'relative z-10 w-full overflow-hidden rounded-xl border border-line-subtle bg-elevated shadow-pop',
              sizeClasses[size],
            ].join(' ')}
            role="dialog"
            aria-modal="true"
          >
            {(title || showCloseButton) && (
              <div className="flex items-start justify-between gap-4 border-b border-line-subtle px-6 py-4">
                <div className="min-w-0">
                  {title && (
                    <h2 className="text-h4 font-semibold text-ink-1">{title}</h2>
                  )}
                  {description && (
                    <p className="mt-1 text-small text-ink-3">{description}</p>
                  )}
                </div>
                {showCloseButton && (
                  <button
                    onClick={onClose}
                    aria-label="关闭"
                    className="ds-btn-ghost flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-md text-ink-3"
                  >
                    <X size={16} />
                  </button>
                )}
              </div>
            )}

            <div className="px-6 py-5">{children}</div>

            {footer && (
              <div className="flex items-center justify-end gap-2 border-t border-line-subtle bg-surface/50 px-6 py-3">
                {footer}
              </div>
            )}
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
};

export default Modal;
