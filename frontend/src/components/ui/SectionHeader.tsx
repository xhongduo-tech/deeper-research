import React from 'react';

interface SectionHeaderProps {
  eyebrow?: React.ReactNode;
  title: React.ReactNode;
  description?: React.ReactNode;
  align?: 'start' | 'center';
  actions?: React.ReactNode;
  size?: 'sm' | 'md' | 'lg';
}

const titleClass = {
  sm: 'text-h3',
  md: 'text-h2',
  lg: 'text-h1',
};

export const SectionHeader: React.FC<SectionHeaderProps> = ({
  eyebrow,
  title,
  description,
  align = 'start',
  actions,
  size = 'md',
}) => {
  return (
    <div
      className={[
        'flex flex-col gap-2 md:flex-row md:items-end md:gap-6',
        align === 'center' ? 'md:justify-center' : 'md:justify-between',
      ].join(' ')}
    >
      <div
        className={[
          'flex flex-col gap-2 max-w-3xl',
          align === 'center' ? 'text-center md:mx-auto' : '',
        ].join(' ')}
      >
        {eyebrow && <span className="ds-eyebrow">{eyebrow}</span>}
        <h2 className={[titleClass[size], 'font-semibold text-ink-1 text-balance'].join(' ')}>
          {title}
        </h2>
        {description && (
          <p className="text-ink-3 text-lead text-pretty leading-relaxed">{description}</p>
        )}
      </div>
      {actions && <div className="flex flex-shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
};

export default SectionHeader;
