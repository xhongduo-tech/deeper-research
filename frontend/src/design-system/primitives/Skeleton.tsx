import React from 'react';
import { cn } from '../utils';

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  width?: number | string;
  height?: number | string;
  radius?: 'sm' | 'md' | 'lg' | 'full';
  /** circle = 圆形占位 */
  circle?: boolean;
}

const radiusCls = {
  sm: 'rounded-sm',
  md: 'rounded-md',
  lg: 'rounded-lg',
  full: 'rounded-full',
} as const;

/**
 * Skeleton primitive v3
 * - 统一 shimmer：在 sunken 和 mist 之间渐变
 */
export const Skeleton: React.FC<SkeletonProps> = ({
  width,
  height,
  radius = 'md',
  circle,
  className,
  style,
  ...rest
}) => {
  return (
    <div
      className={cn(
        'relative overflow-hidden bg-sunken',
        circle ? 'rounded-full' : radiusCls[radius],
        'animate-shimmer',
        className,
      )}
      style={{
        width,
        height,
        backgroundImage:
          'linear-gradient(90deg, #f5f4f0 0%, #ececea 40%, #ececea 60%, #f5f4f0 100%)',
        backgroundSize: '200% 100%',
        ...style,
      }}
      {...rest}
    />
  );
};

export const SkeletonText: React.FC<{
  lines?: number;
  lastLineWidth?: string;
  className?: string;
}> = ({ lines = 3, lastLineWidth = '60%', className }) => (
  <div className={cn('space-y-2', className)}>
    {Array.from({ length: lines }).map((_, i) => (
      <Skeleton
        key={i}
        height={12}
        width={i === lines - 1 ? lastLineWidth : '100%'}
      />
    ))}
  </div>
);

export default Skeleton;
