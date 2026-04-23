import React, { forwardRef } from 'react';

interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  padding?: 'none' | 'sm' | 'md' | 'lg';
  interactive?: boolean;
  as?: 'div' | 'section' | 'article';
}

const paddingClass = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-7',
};

export const Card = forwardRef<HTMLDivElement, CardProps>(
  ({ padding = 'md', interactive, as = 'div', className = '', children, ...rest }, ref) => {
    const Tag = as as any;
    return (
      <Tag
        ref={ref}
        className={[
          'ds-card',
          paddingClass[padding],
          interactive ? 'ds-card-hover cursor-pointer' : '',
          className,
        ]
          .filter(Boolean)
          .join(' ')}
        {...rest}
      >
        {children}
      </Tag>
    );
  },
);

Card.displayName = 'Card';

interface CardHeaderProps extends Omit<React.HTMLAttributes<HTMLDivElement>, 'title'> {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
}

export const CardHeader: React.FC<CardHeaderProps> = ({
  title,
  description,
  icon,
  actions,
  className = '',
  ...rest
}) => (
  <div
    className={['flex items-start gap-3', className].filter(Boolean).join(' ')}
    {...rest}
  >
    {icon && (
      <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-md bg-brand-soft text-brand">
        {icon}
      </span>
    )}
    <div className="min-w-0 flex-1">
      <h3 className="text-h4 font-semibold text-ink-1">{title}</h3>
      {description && <p className="mt-1 text-small text-ink-3">{description}</p>}
    </div>
    {actions && <div className="flex flex-shrink-0 items-center gap-2">{actions}</div>}
  </div>
);

export default Card;
