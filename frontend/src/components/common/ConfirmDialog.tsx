import React from 'react';
import { AlertTriangle } from 'lucide-react';
import { Dialog, Button } from '../../design-system';

interface ConfirmDialogProps {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  message: React.ReactNode;
  confirmText?: string;
  cancelText?: string;
  variant?: 'danger' | 'warning' | 'info';
  loading?: boolean;
}

const variantConfig = {
  danger: {
    label: '确认删除',
    iconColor: 'text-danger',
    iconBg: 'bg-danger-soft',
    confirmVariant: 'danger' as const,
  },
  warning: {
    label: '确认操作',
    iconColor: 'text-warning',
    iconBg: 'bg-warning-soft',
    confirmVariant: 'primary' as const,
  },
  info: {
    label: '确认',
    iconColor: 'text-info',
    iconBg: 'bg-info-soft',
    confirmVariant: 'primary' as const,
  },
};

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  onClose,
  onConfirm,
  title,
  message,
  confirmText,
  cancelText = '取消',
  variant = 'warning',
  loading = false,
}) => {
  const config = variantConfig[variant];

  return (
    <Dialog
      open={open}
      onClose={onClose}
      size="sm"
      closable={false}
      dismissOnBackdrop={!loading}
    >
      <div className="flex flex-col items-center text-center gap-4 py-1">
        <div
          className={[
            'flex h-12 w-12 items-center justify-center rounded-full',
            config.iconBg,
          ].join(' ')}
        >
          <AlertTriangle size={22} className={config.iconColor} />
        </div>

        <div className="space-y-1.5">
          <h3 className="text-[16px] font-semibold text-ink-1">{title}</h3>
          <p className="text-[13px] leading-relaxed text-ink-2">{message}</p>
        </div>

        <div className="mt-2 flex w-full gap-3">
          <Button
            variant="secondary"
            onClick={onClose}
            disabled={loading}
            className="flex-1"
          >
            {cancelText}
          </Button>
          <Button
            variant={config.confirmVariant}
            onClick={onConfirm}
            loading={loading}
            className="flex-1"
          >
            {confirmText || config.label}
          </Button>
        </div>
      </div>
    </Dialog>
  );
};

export default ConfirmDialog;
