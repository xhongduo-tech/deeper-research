import React from 'react';

interface ToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  disabled?: boolean;
  tone?: 'brand' | 'cedar';
}

export const Toggle: React.FC<ToggleProps> = ({
  checked,
  onChange,
  label,
  description,
  icon,
  disabled,
  tone = 'brand',
}) => {
  const activeBg = tone === 'brand' ? 'bg-brand' : 'bg-cedar';
  return (
    <label
      className={[
        'flex items-start justify-between gap-3 rounded-lg border p-4 transition-colors',
        checked
          ? tone === 'brand'
            ? 'border-brand/40 bg-brand-soft/30'
            : 'border-cedar/40 bg-cedar-soft/40'
          : 'border-line-subtle bg-elevated',
        disabled ? 'opacity-60' : '',
      ].join(' ')}
    >
      <div className="flex min-w-0 items-start gap-3">
        {icon && (
          <span
            className={[
              'flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md',
              checked ? 'bg-white/60 text-brand' : 'bg-sunken text-ink-3',
            ].join(' ')}
          >
            {icon}
          </span>
        )}
        <div className="min-w-0">
          {label && <div className="text-body font-medium text-ink-1">{label}</div>}
          {description && (
            <div className="mt-0.5 text-small text-ink-3">{description}</div>
          )}
        </div>
      </div>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => !disabled && onChange(!checked)}
        disabled={disabled}
        className={[
          'relative h-6 w-11 flex-shrink-0 rounded-full transition-colors duration-200',
          checked ? activeBg : 'bg-line',
          'focus-visible:shadow-ring-brand',
        ].join(' ')}
      >
        <span
          className="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform duration-200"
          style={{ transform: checked ? 'translateX(22px)' : 'translateX(2px)' }}
        />
      </button>
    </label>
  );
};

interface SwitchProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  size?: 'sm' | 'md';
  tone?: 'brand' | 'cedar';
  label?: string;
}

export const Switch: React.FC<SwitchProps> = ({
  checked,
  onChange,
  disabled,
  size = 'md',
  tone = 'brand',
  label,
}) => {
  const h = size === 'sm' ? 'h-5 w-9' : 'h-6 w-11';
  const knob = size === 'sm' ? 'h-4 w-4' : 'h-5 w-5';
  const offset = checked
    ? size === 'sm'
      ? 'translateX(18px)'
      : 'translateX(22px)'
    : 'translateX(2px)';
  const active = tone === 'brand' ? 'bg-brand' : 'bg-cedar';

  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={[
        'relative flex-shrink-0 rounded-full transition-colors duration-200',
        h,
        checked ? active : 'bg-line',
        disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer',
      ].join(' ')}
    >
      <span
        className={[
          'absolute top-0.5 rounded-full bg-white shadow transition-transform duration-200',
          knob,
        ].join(' ')}
        style={{ transform: offset }}
      />
    </button>
  );
};

export default Toggle;
