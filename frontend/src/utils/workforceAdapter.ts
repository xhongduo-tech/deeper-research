import type { Employee } from '../types';
import type { WorkforceMember } from '../types/report';

/**
 * Adapt a v2 `WorkforceMember` to the legacy `Employee` shape expected by
 * `EmployeeCard`. Defensive about nullable / missing fields so a partial
 * server payload never crashes the page.
 */
export function toLegacyEmployee(m: Partial<WorkforceMember> | null | undefined): Employee {
  const rec = (m ?? {}) as Partial<WorkforceMember>;
  return {
    id: rec.id ?? 'unknown',
    name: rec.name ?? rec.first_name_en ?? '未命名员工',
    name_en: rec.first_name_en ?? '',
    description: rec.tagline_en || rec.description || '',
    avatar_emoji: '',
    avatar_color: '#141414',
    skills: Array.isArray(rec.skills) ? rec.skills : [],
    tools: Array.isArray(rec.tools) ? rec.tools : [],
    default_model:
      rec.default_model ||
      [rec.resolved_model_name, rec.resolved_model_id].filter(Boolean).join(' · ') ||
      undefined,
    category: rec.category ?? 'operations',
    enabled: rec.enabled !== false,
  };
}
