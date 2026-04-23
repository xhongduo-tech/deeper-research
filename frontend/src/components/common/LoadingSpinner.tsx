import React from 'react';
import { BrandMark } from '../ui/BrandMark';

interface LoadingSpinnerProps {
  size?: 'sm' | 'md' | 'lg';
  color?: string;
  text?: string;
  fullScreen?: boolean;
}

const sizeMap = {
  sm: 'w-4 h-4 border-2',
  md: 'w-7 h-7 border-2',
  lg: 'w-11 h-11 border-[3px]',
};

export const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
  size = 'md',
  color = 'var(--color-brand)',
  text,
  fullScreen = false,
}) => {
  const spinner = (
    <div className="flex flex-col items-center gap-3">
      <div
        className={`${sizeMap[size]} rounded-full border-line-subtle border-t-transparent animate-spin`}
        style={{ borderTopColor: color }}
      />
      {text && <span className="animate-pulse text-small text-ink-3">{text}</span>}
    </div>
  );

  if (fullScreen) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-canvas">
        {spinner}
      </div>
    );
  }

  return spinner;
};

export const ThinkingDots: React.FC<{ color?: string; size?: number }> = ({
  color = 'var(--color-cedar)',
  size = 5,
}) => (
  <span className="inline-flex items-center gap-1">
    {[0, 1, 2].map((i) => (
      <span
        key={i}
        className="inline-block rounded-full"
        style={{
          width: `${size}px`,
          height: `${size}px`,
          backgroundColor: color,
          animation: `thinking 1.4s ease-in-out ${i * 0.18}s infinite`,
        }}
      />
    ))}
  </span>
);

export const PageLoader: React.FC<{ text?: string }> = ({ text = '加载中...' }) => (
  <div className="flex min-h-[360px] flex-col items-center justify-center gap-5">
    <div className="relative">
      <BrandMark size={48} />
      <span
        className="absolute -inset-2 rounded-xl"
        style={{ animation: 'pulseRing 2.2s ease-in-out infinite' }}
      />
    </div>
    <p className="text-small text-ink-3">{text}</p>
  </div>
);

export default LoadingSpinner;
