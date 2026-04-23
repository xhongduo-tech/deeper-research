import React from 'react';
import type { TaskStatus } from '../../types';
import { TASK_STATUS_LABELS } from '../../utils/constants';
import { Badge, type BadgeTone } from '../ui/Badge';

interface StatusBadgeProps {
  status: TaskStatus | string;
  showDot?: boolean;
  size?: 'sm' | 'md';
}

const ANIMATED_STATUSES = ['enriching', 'executing', 'evaluating', 'refining'];

const STATUS_TONE: Record<string, BadgeTone> = {
  pending: 'neutral',
  enriching: 'warning',
  waiting_approval: 'brand',
  executing: 'cedar',
  evaluating: 'cedar',
  refining: 'warning',
  completed: 'success',
  failed: 'danger',
};

export const StatusBadge: React.FC<StatusBadgeProps> = ({
  status,
  showDot = true,
  size = 'md',
}) => {
  const label = TASK_STATUS_LABELS[status] || status;
  const tone = STATUS_TONE[status] || 'neutral';
  const isAnimated = ANIMATED_STATUSES.includes(status);

  return (
    <Badge
      tone={tone}
      variant="soft"
      size={size === 'md' ? 'sm' : 'xs'}
      dot={showDot}
      animatedDot={isAnimated}
    >
      {label}
    </Badge>
  );
};

interface AgentStatusBadgeProps {
  status: 'idle' | 'running' | 'completed' | 'failed';
}

const AGENT_TONE: Record<AgentStatusBadgeProps['status'], BadgeTone> = {
  idle: 'neutral',
  running: 'cedar',
  completed: 'success',
  failed: 'danger',
};

const AGENT_LABEL: Record<AgentStatusBadgeProps['status'], string> = {
  idle: '待命',
  running: '执行中',
  completed: '已完成',
  failed: '失败',
};

export const AgentStatusBadge: React.FC<AgentStatusBadgeProps> = ({ status }) => (
  <Badge
    tone={AGENT_TONE[status]}
    variant="soft"
    size="xs"
    dot
    animatedDot={status === 'running'}
  >
    {AGENT_LABEL[status]}
  </Badge>
);

export default StatusBadge;
