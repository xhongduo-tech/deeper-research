import React from 'react';
import { Users } from 'lucide-react';
import type { Employee, AgentStatus } from '../../types';
import { EmployeeCard } from './EmployeeCard';

interface EmployeeGridProps {
  employees: Employee[];
  agentStatuses?: Record<string, AgentStatus>;
  compact?: boolean;
  selectable?: boolean;
  selectedIds?: string[];
  onToggleSelect?: (id: string) => void;
}

export const EmployeeGrid: React.FC<EmployeeGridProps> = ({
  employees,
  agentStatuses = {},
  compact = false,
  selectable = false,
  selectedIds = [],
  onToggleSelect,
}) => {
  if (employees.length === 0) {
    return (
      <div className="ds-card flex flex-col items-center gap-3 p-10 text-center">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-sunken text-ink-3">
          <Users size={18} />
        </span>
        <p className="text-small text-ink-3">暂无智能员工</p>
      </div>
    );
  }

  return (
    <div
      className={
        compact
          ? 'grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3'
          : // 竖版身份牌 3:4，每张偏宽。xl 最多 4 列，2xl 5 列。
            'grid grid-cols-2 gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-3 xl:grid-cols-4 2xl:grid-cols-5'
      }
    >
      {employees.map((employee, idx) => (
        <EmployeeCard
          key={employee.id}
          index={idx + 1}
          employee={employee}
          status={agentStatuses[employee.id]}
          compact={compact}
          selectable={selectable}
          selected={selectedIds.includes(employee.id)}
          onSelect={() => onToggleSelect?.(employee.id)}
        />
      ))}
    </div>
  );
};

export default EmployeeGrid;
