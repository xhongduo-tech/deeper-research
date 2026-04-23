/**
 * 深研 AI · Design System v3
 * 见 /DESIGN.md §5
 *
 * 所有新页面优先从这里导入 primitives。
 * Legacy components 在 src/components/ui/* 仍然可用但不推荐。
 */

export { Button } from './primitives/Button';
export type { ButtonProps, ButtonVariant, ButtonSize } from './primitives/Button';

export { Input } from './primitives/Input';
export type { InputProps } from './primitives/Input';

export { Textarea } from './primitives/Textarea';
export type { TextareaProps } from './primitives/Textarea';

export { Select } from './primitives/Select';
export type { SelectProps, SelectOption } from './primitives/Select';

export { Dialog } from './primitives/Dialog';
export type { DialogProps } from './primitives/Dialog';

export { Tabs } from './primitives/Tabs';
export type { TabsProps, TabItem } from './primitives/Tabs';

export { Badge } from './primitives/Badge';
export type { BadgeProps, BadgeTone, BadgeVariant } from './primitives/Badge';

export { ProgressRing } from './primitives/ProgressRing';
export type { ProgressRingProps } from './primitives/ProgressRing';

export { Skeleton, SkeletonText } from './primitives/Skeleton';
export type { SkeletonProps } from './primitives/Skeleton';

export { Switch } from './primitives/Switch';
export type { SwitchProps } from './primitives/Switch';

export { EmptyState, ErrorState, LoadingState } from './primitives/States';
export type {
  EmptyStateProps,
  ErrorStateProps,
  LoadingStateProps,
} from './primitives/States';

export { cn } from './utils';
export * as tokens from './tokens';
