import React from 'react';
import { cn } from '../utils';

export interface SwitchProps {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  size?: 'sm' | 'md';
  label?: React.ReactNode;
  description?: React.ReactNode;
  id?: string;
  className?: string;
}

const trackSize = {
  sm: { w: 28, h: 16, knob: 12, pad: 2 },
  md: { w: 36, h: 20, knob: 16, pad: 2 },
};

export const Switch: React.FC<SwitchProps> = ({
  checked,
  onChange,
  disabled,
  size = 'md',
  label,
  description,
  id,
  className,
}) => {
  const s = trackSize[size];
  const uid = React.useId();
  const controlId = id ?? uid;

  const control = (
    <button
      role="switch"
      type="button"
      id={controlId}
      aria-checked={checked}
      disabled={disabled}
      onClick={() => !disabled && onChange(!checked)}
      className={cn(
        'relative flex-shrink-0 inline-flex items-center rounded-full',
        'transition-colors duration-base',
        'focus-visible:outline-none focus-visible:shadow-ring-brand',
        checked ? 'bg-brand' : 'bg-mist',
        disabled && 'opacity-55 cursor-not-allowed',
      )}
      style={{ width: s.w, height: s.h }}
    >
      <span
        className="absolute bg-white rounded-full shadow-sm transition-transform duration-base ease-[cubic-bezier(0.2,0,0,1)]"
        style={{
          width: s.knob,
          height: s.knob,
          top: s.pad,
          left: s.pad,
          transform: checked
            ? `translateX(${s.w - s.knob - s.pad * 2}px)`
            : 'translateX(0)',
        }}
      />
    </button>
  );

  if (!label && !description) return <div className={className}>{control}</div>;

  return (
    <label
      htmlFor={controlId}
      className={cn(
        'flex items-start gap-3 cursor-pointer',
        disabled && 'cursor-not-allowed',
        className,
      )}
    >
      {control}
      <span className="min-w-0 flex-1">
        {label && (
          <span className="block text-[13.5px] font-medium text-ink-1">
            {label}
          </span>
        )}
        {description && (
          <span className="mt-0.5 block text-[12px] text-ink-3">
            {description}
          </span>
        )}
      </span>
    </label>
  );
};

export default Switch;
