import React, { forwardRef } from 'react';

type BaseInputProps = React.InputHTMLAttributes<HTMLInputElement> & {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  leftAddon?: React.ReactNode;
  rightAddon?: React.ReactNode;
  containerClassName?: string;
};

export const Input = forwardRef<HTMLInputElement, BaseInputProps>(
  (
    {
      label,
      hint,
      error,
      leftAddon,
      rightAddon,
      className = '',
      containerClassName = '',
      id,
      ...rest
    },
    ref,
  ) => {
    const inputId = id || rest.name;
    return (
      <div className={['flex flex-col gap-1.5', containerClassName].filter(Boolean).join(' ')}>
        {label && (
          <label htmlFor={inputId} className="text-small font-medium text-ink-2">
            {label}
          </label>
        )}
        <div className="relative">
          {leftAddon && (
            <span className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-ink-3">
              {leftAddon}
            </span>
          )}
          <input
            ref={ref}
            id={inputId}
            className={[
              'ds-input',
              leftAddon ? 'pl-10' : '',
              rightAddon ? 'pr-10' : '',
              error ? 'border-danger focus:border-danger' : '',
              className,
            ]
              .filter(Boolean)
              .join(' ')}
            {...rest}
          />
          {rightAddon && (
            <span className="absolute inset-y-0 right-2 flex items-center text-ink-3">
              {rightAddon}
            </span>
          )}
        </div>
        {error ? (
          <span className="text-small text-danger">{error}</span>
        ) : (
          hint && <span className="text-small text-ink-3">{hint}</span>
        )}
      </div>
    );
  },
);

Input.displayName = 'Input';

type TextareaProps = React.TextareaHTMLAttributes<HTMLTextAreaElement> & {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  showCount?: boolean;
  containerClassName?: string;
};

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      label,
      hint,
      error,
      showCount,
      className = '',
      containerClassName = '',
      id,
      value,
      maxLength,
      ...rest
    },
    ref,
  ) => {
    const textareaId = id || rest.name;
    const length = typeof value === 'string' ? value.length : 0;
    return (
      <div className={['flex flex-col gap-1.5', containerClassName].filter(Boolean).join(' ')}>
        {label && (
          <label htmlFor={textareaId} className="text-small font-medium text-ink-2">
            {label}
          </label>
        )}
        <textarea
          ref={ref}
          id={textareaId}
          value={value}
          maxLength={maxLength}
          className={[
            'ds-input resize-none leading-relaxed',
            error ? 'border-danger focus:border-danger' : '',
            className,
          ]
            .filter(Boolean)
            .join(' ')}
          {...rest}
        />
        <div className="flex items-center justify-between gap-2">
          {error ? (
            <span className="text-small text-danger">{error}</span>
          ) : hint ? (
            <span className="text-small text-ink-3">{hint}</span>
          ) : (
            <span />
          )}
          {showCount && (
            <span className="text-caption text-ink-4">
              {length}
              {maxLength ? ` / ${maxLength}` : ''}
            </span>
          )}
        </div>
      </div>
    );
  },
);

Textarea.displayName = 'Textarea';

export default Input;
