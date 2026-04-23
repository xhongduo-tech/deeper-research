import React, { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Edit2,
  Save,
  RefreshCw,
  Search,
  Users,
  Bot,
  Layers3,
} from 'lucide-react';
import type { Employee, AgentConfig, SystemConfig, LlmProfile } from '../../types';
import {
  updateAgentConfig,
  createAgentConfig,
  applyDefaultConfig,
} from '../../api/admin';
import { Dialog } from '../../design-system';
import { EMPLOYEE_CATEGORIES } from '../../utils/constants';
import { Button, Input, Switch, Badge } from '../ui';
import toast from 'react-hot-toast';

interface EmployeeConfigProps {
  employees: Employee[];
  agentConfigs: AgentConfig[];
  systemConfig?: SystemConfig | null;
  onConfigUpdated: () => void;
}

interface EditModalState {
  open: boolean;
  employee: Employee | null;
  config: Partial<AgentConfig>;
}

interface ApplyDefaultState {
  open: boolean;
  model_profile_id: string;
}

function getProfileId(config?: Partial<AgentConfig> | null): string {
  return (
    config?.model_profile_id ||
    (config?.custom_params as Record<string, unknown> | undefined)?.model_profile_id as string ||
    ''
  );
}

function resolveProfile(
  config: Partial<AgentConfig> | undefined,
  profiles: LlmProfile[]
): LlmProfile | undefined {
  if (!config) return undefined;
  const profileId = getProfileId(config);
  if (profileId) {
    return profiles.find((profile) => profile.id === profileId);
  }
  if (config.llm_model) {
    return profiles.find((profile) => profile.model === config.llm_model);
  }
  return undefined;
}

export const EmployeeConfig: React.FC<EmployeeConfigProps> = ({
  employees,
  agentConfigs,
  systemConfig,
  onConfigUpdated,
}) => {
  const profiles = systemConfig?.llm_profiles || [];
  const defaultProfileId = systemConfig?.default_llm_profile_id || profiles[0]?.id || '';

  const [editModal, setEditModal] = useState<EditModalState>({
    open: false,
    employee: null,
    config: {},
  });
  const [applyDefault, setApplyDefault] = useState<ApplyDefaultState>({
    open: false,
    model_profile_id: defaultProfileId,
  });
  const [saving, setSaving] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [categoryFilter, setCategoryFilter] = useState('');

  const categories = useMemo(
    () => [...new Set(employees.map((e) => e.category))],
    [employees]
  );
  const selectedBulkProfile = useMemo(
    () =>
      profiles.find(
        (profile) => profile.id === (applyDefault.model_profile_id || defaultProfileId),
      ),
    [applyDefault.model_profile_id, defaultProfileId, profiles],
  );

  useEffect(() => {
    setApplyDefault((prev) => ({
      ...prev,
      model_profile_id: prev.model_profile_id || defaultProfileId,
    }));
  }, [defaultProfileId]);

  const getConfig = (employeeId: string) =>
    agentConfigs.find((c) => c.employee_id === employeeId);

  const filteredEmployees = employees.filter((e) => {
    const matchSearch =
      !searchQuery ||
      e.name.includes(searchQuery) ||
      e.name_en.toLowerCase().includes(searchQuery.toLowerCase());
    const matchCategory = !categoryFilter || e.category === categoryFilter;
    return matchSearch && matchCategory;
  });

  const openEditModal = (employee: Employee) => {
    const config = getConfig(employee.id);
    setEditModal({
      open: true,
      employee,
      config: config
        ? { ...config, model_profile_id: getProfileId(config) }
        : {
            employee_id: employee.id,
            model_profile_id: defaultProfileId,
            enabled: true,
          },
    });
  };

  const handleSave = async () => {
    if (!editModal.employee) return;
    if (!profiles.length) {
      toast.error('请先在系统设置中配置至少一个模型');
      return;
    }
    if (!editModal.config.model_profile_id) {
      toast.error('请选择模型');
      return;
    }

    setSaving(true);
    try {
      const payload: Partial<AgentConfig> & {
        employee_id: string;
        model_profile_id: string;
        custom_params?: Record<string, unknown>;
      } = {
        employee_id: editModal.employee.id,
        model_profile_id: String(editModal.config.model_profile_id),
        enabled: editModal.config.enabled ?? true,
        custom_params: {
          ...(editModal.config.custom_params || {}),
          model_profile_id: String(editModal.config.model_profile_id),
        },
      };

      const existing = getConfig(editModal.employee.id);
      if (existing) {
        await updateAgentConfig(existing.id, payload);
      } else {
        await createAgentConfig(payload as Omit<AgentConfig, 'id'>);
      }
      toast.success('员工模型配置已保存');
      onConfigUpdated();
      setEditModal({ open: false, employee: null, config: {} });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleApplyDefault = async () => {
    setSaving(true);
    try {
      await applyDefaultConfig({
        model_profile_id: applyDefault.model_profile_id || defaultProfileId,
      });
      toast.success('所选模型已应用到未单独配置的员工');
      onConfigUpdated();
      setApplyDefault({ open: false, model_profile_id: defaultProfileId });
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || '批量应用失败');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <Input
          containerClassName="min-w-[220px] flex-1"
          leftAddon={<Search size={14} />}
          placeholder="搜索员工姓名或 name_en..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="ds-input max-w-[180px]"
        >
          <option value="">所有分类</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {EMPLOYEE_CATEGORIES[c] || c}
            </option>
          ))}
        </select>
        <Button
          variant="outline"
          size="md"
          leftIcon={<RefreshCw size={14} />}
          onClick={() => setApplyDefault({ open: true, model_profile_id: defaultProfileId })}
          disabled={!profiles.length}
        >
          批量应用模型
        </Button>
      </div>

      {!profiles.length && (
        <div className="rounded-xl border border-warning/30 bg-warning/5 px-4 py-3 text-[13px] text-warning">
          尚未配置模型池。请先到「系统设置」中新增至少一个模型配置，然后再为员工选择模型。
        </div>
      )}

      <div className="ds-card overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full text-[13.5px]">
            <thead>
              <tr className="border-b border-line bg-surface">
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  员工
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  分类
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  所选模型
                </th>
                <th className="px-4 py-3 text-left text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  状态
                </th>
                <th className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-ink-3">
                  操作
                </th>
              </tr>
            </thead>
            <tbody>
              {filteredEmployees.map((employee, i) => {
                const config = getConfig(employee.id);
                const profile =
                  resolveProfile(config, profiles) ||
                  (!config
                    ? profiles.find((candidate) => candidate.id === defaultProfileId)
                    : undefined);
                return (
                  <motion.tr
                    key={employee.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    transition={{ delay: i * 0.02 }}
                    className="border-b border-line-subtle transition-colors hover:bg-surface/60"
                  >
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2.5">
                        <div
                          className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-full text-base"
                          style={{ backgroundColor: `${employee.avatar_color}22` }}
                        >
                          {employee.avatar_emoji}
                        </div>
                        <div className="min-w-0">
                          <div className="truncate text-[13px] font-medium text-ink-1">
                            {employee.name}
                          </div>
                          <div className="truncate text-[11.5px] text-ink-3">
                            {employee.name_en}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className="inline-flex rounded-full px-2 py-0.5 text-[11.5px]"
                        style={{
                          backgroundColor: `${employee.avatar_color}1e`,
                          color: employee.avatar_color,
                        }}
                      >
                        {EMPLOYEE_CATEGORIES[employee.category] || employee.category}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      {profile ? (
                        <div className="space-y-0.5">
                          <div className="text-[12.5px] font-medium text-ink-1">
                            {profile.name}
                            {!config && (
                              <span className="ml-1 text-[11px] font-normal text-ink-3">
                                （系统默认）
                              </span>
                            )}
                          </div>
                          <div className="font-mono text-[11.5px] text-ink-3">{profile.model}</div>
                        </div>
                      ) : config?.llm_model ? (
                        <div className="space-y-0.5">
                          <div className="text-[12.5px] font-medium text-ink-1">旧版单独配置</div>
                          <div className="font-mono text-[11.5px] text-ink-3">{config.llm_model}</div>
                        </div>
                      ) : (
                        <span className="text-[12px] italic text-ink-4">未配置</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      {config?.enabled !== false ? (
                        <Badge tone="success" variant="soft" dot>
                          已启用
                        </Badge>
                      ) : (
                        <Badge tone="neutral" variant="soft">
                          已禁用
                        </Badge>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        leftIcon={<Edit2 size={12} />}
                        onClick={() => openEditModal(employee)}
                      >
                        编辑
                      </Button>
                    </td>
                  </motion.tr>
                );
              })}
            </tbody>
          </table>
        </div>

        {filteredEmployees.length === 0 && (
          <div className="flex flex-col items-center gap-2 py-12 text-ink-3">
            <Users size={20} className="text-ink-4" />
            <span className="text-[13px]">没有找到匹配的员工</span>
          </div>
        )}
      </div>

      <Dialog
        open={editModal.open}
        onClose={() => setEditModal({ open: false, employee: null, config: {} })}
        title={`配置 ${editModal.employee?.name || ''}`}
        size="md"
      >
        {editModal.employee && (
          <div className="space-y-4">
            <div className="flex items-center gap-3 rounded-lg border border-line-subtle bg-surface p-3">
              <div
                className="flex h-11 w-11 items-center justify-center rounded-full text-xl"
                style={{ backgroundColor: `${editModal.employee.avatar_color}22` }}
              >
                {editModal.employee.avatar_emoji}
              </div>
              <div className="min-w-0">
                <p className="truncate text-[14px] font-medium text-ink-1">
                  {editModal.employee.name}
                </p>
                <p className="truncate text-[12px] text-ink-3">
                  {editModal.employee.description?.slice(0, 80)}…
                </p>
              </div>
            </div>

            <div className="rounded-lg border border-line-subtle bg-surface p-4">
              <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-ink-1">
                <Bot size={14} />
                选择模型
              </div>
              <select
                value={String(editModal.config.model_profile_id || '')}
                onChange={(e) =>
                  setEditModal((prev) => ({
                    ...prev,
                    config: {
                      ...prev.config,
                      model_profile_id: e.target.value,
                    },
                  }))
                }
                className="ds-input w-full"
                disabled={!profiles.length}
              >
                <option value="">请选择一个模型配置</option>
                {profiles.map((profile) => (
                  <option key={profile.id} value={profile.id}>
                    {profile.name} · {profile.model}
                  </option>
                ))}
              </select>
              {resolveProfile(editModal.config, profiles) && (
                <div className="mt-3 rounded-md border border-line-subtle bg-paper px-3 py-2 text-[12px] text-ink-3">
                  <div className="font-medium text-ink-1">
                    {resolveProfile(editModal.config, profiles)?.name}
                  </div>
                  <div className="font-mono">{resolveProfile(editModal.config, profiles)?.model}</div>
                  <div className="truncate">{resolveProfile(editModal.config, profiles)?.base_url}</div>
                </div>
              )}
            </div>

            <div className="flex items-center justify-between rounded-lg border border-line-subtle bg-surface px-4 py-3">
              <div>
                <div className="text-[13.5px] font-medium text-ink-1">启用此员工</div>
                <div className="text-[11.5px] text-ink-3">禁用后将不会参与任务编排</div>
              </div>
              <Switch
                checked={editModal.config.enabled !== false}
                onChange={(v) =>
                  setEditModal((prev) => ({
                    ...prev,
                    config: { ...prev.config, enabled: v },
                  }))
                }
              />
            </div>

            <div className="flex gap-3 pt-2">
              <Button
                variant="outline"
                fullWidth
                onClick={() => setEditModal({ open: false, employee: null, config: {} })}
              >
                取消
              </Button>
              <Button
                variant="primary"
                fullWidth
                loading={saving}
                leftIcon={!saving ? <Save size={14} /> : undefined}
                onClick={handleSave}
              >
                {saving ? '保存中…' : '保存配置'}
              </Button>
            </div>
          </div>
        )}
      </Dialog>

      <Dialog
        open={applyDefault.open}
        onClose={() => setApplyDefault({ open: false, model_profile_id: defaultProfileId })}
        title="批量应用模型"
        size="md"
      >
        <div className="space-y-4">
          <p className="text-[13px] leading-relaxed text-ink-2">
            只会应用到当前还没有单独配置的员工；已经有单独模型配置的员工不会被覆盖。
          </p>

          <div>
            <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-ink-1">
              <Bot size={14} />
              选择要批量应用的模型
            </div>
            <select
              value={applyDefault.model_profile_id || defaultProfileId}
              onChange={(e) =>
                setApplyDefault((prev) => ({
                  ...prev,
                  model_profile_id: e.target.value,
                }))
              }
              className="ds-input w-full"
            >
              {profiles.map((profile) => (
                <option key={profile.id} value={profile.id}>
                  {profile.name} · {profile.model}
                </option>
              ))}
            </select>
          </div>

          <div className="rounded-lg border border-line-subtle bg-surface p-4">
            <div className="mb-2 flex items-center gap-2 text-[13px] font-medium text-ink-1">
              <Layers3 size={14} />
              即将应用的模型
            </div>
            {selectedBulkProfile ? (
              <div className="space-y-0.5 text-[12px] text-ink-3">
                <div className="font-medium text-ink-1">
                  {selectedBulkProfile.name}
                  {selectedBulkProfile.id === defaultProfileId && (
                    <span className="ml-1 text-[11px] text-ink-3">（系统默认）</span>
                  )}
                </div>
                <div className="font-mono">{selectedBulkProfile.model}</div>
                <div>{selectedBulkProfile.base_url}</div>
              </div>
            ) : (
              <div className="text-[12px] text-ink-3">未选择模型</div>
            )}
          </div>

          <div className="flex gap-3 pt-2">
            <Button
              variant="outline"
              fullWidth
              onClick={() => setApplyDefault({ open: false, model_profile_id: defaultProfileId })}
            >
              取消
            </Button>
            <Button
              variant="primary"
              fullWidth
              loading={saving}
              onClick={handleApplyDefault}
              disabled={!defaultProfileId}
            >
              {saving ? '应用中…' : '批量应用'}
            </Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
};

export default EmployeeConfig;
