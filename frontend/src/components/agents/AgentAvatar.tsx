import React from 'react';

interface AgentAvatarProps {
  emoji: string;
  color: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  active?: boolean;
  completed?: boolean;
  failed?: boolean;
}

const sizeMap = {
  sm: { outer: 'w-8 h-8', emoji: 'text-base', dot: 'w-2.5 h-2.5' },
  md: { outer: 'w-10 h-10', emoji: 'text-xl', dot: 'w-2.5 h-2.5' },
  lg: { outer: 'w-14 h-14', emoji: 'text-2xl', dot: 'w-3 h-3' },
  xl: { outer: 'w-20 h-20', emoji: 'text-4xl', dot: 'w-3.5 h-3.5' },
};

export const AgentAvatar: React.FC<AgentAvatarProps> = ({
  emoji,
  color,
  size = 'md',
  active = false,
  completed = false,
  failed = false,
}) => {
  const { outer, emoji: emojiSize, dot } = sizeMap[size];

  const borderColor = failed
    ? 'var(--color-danger)'
    : completed
    ? 'var(--color-success)'
    : active
    ? color
    : 'var(--color-line)';

  return (
    <div className="relative flex-shrink-0">
      <div
        className={`${outer} flex items-center justify-center rounded-full transition-all duration-300`}
        style={{
          backgroundColor: `${color}1c`,
          border: `2px solid ${borderColor}`,
          boxShadow: active ? `0 0 0 4px ${color}26` : 'none',
        }}
      >
        <span className={emojiSize} role="img" aria-label="agent">
          {emoji}
        </span>
      </div>
      {active && (
        <span
          className="absolute inset-0 animate-ping rounded-full opacity-25"
          style={{ backgroundColor: color }}
        />
      )}
      {completed && (
        <span
          className={`absolute -bottom-0.5 -right-0.5 ${dot} rounded-full bg-success border-2 border-elevated`}
          aria-label="completed"
        />
      )}
      {failed && (
        <span
          className={`absolute -bottom-0.5 -right-0.5 ${dot} rounded-full bg-danger border-2 border-elevated`}
          aria-label="failed"
        />
      )}
    </div>
  );
};

export default AgentAvatar;
