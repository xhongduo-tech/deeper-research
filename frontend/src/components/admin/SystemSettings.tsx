import React, { useEffect, useMemo, useState } from 'react';
import {
  Save,
  AlertTriangle,
  Eye,
  EyeOff,
  RefreshCw,
  Wifi,
  WifiOff,
  Bot,
  Database,
  Zap,
  SlidersHorizontal,
  Plus,
  Trash2,
  CheckCircle2,
} from 'lucide-react';
import type { SystemConfig, LlmProfile } from '../../types';
import { updateSystemConfig, testLlmConnection } from '../../api/admin';
import { Button, Input, Switch, CardHeader } from '../ui';
import toast from 'react-hot-toast';

interface SystemSettingsProps {
  config: SystemConfig;
  onConfigUpdated: (config: SystemConfig) => void;
}

interface TestResult {
  success: boolean;
  message: string;
  latency_ms?: number;
}

function slugify(value: string): string {
  return value
    .toLowerCase()
    .trim()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || `profile-${Date.now()}`;
}

function createEmptyProfile(): LlmProfile {
  const stamp = Date.now().toString(36);
  return {
    id: `profile-${stamp}`,
    name: '',
    base_url: '',
    model: '',
    api_key: '',
    description: '',
  };
}

export const SystemSettings: React.FC<SystemSettingsProps> = ({
  config,
  onConfigUpdated,
}) => {
  const [form, setForm] = useState<SystemConfig>({
    ...config,
    llm_profiles: config.llm_profiles || [],
  });
  const [showApiKey, setShowApiKey] = useState(false);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [testingProfileId, setTestingProfileId] = useState<string | null>(null);
  const [testingEmbedding, setTestingEmbedding] = useState(false);
  const [profileTestResults, setProfileTestResults] = useState<Record<string, TestResult | null>>({});
  const [embeddingTestResult, setEmbeddingTestResult] = useState<TestResult | null>(null);

  useEffect(() => {
    setForm({ ...config, llm_profiles: config.llm_profiles || [] });
    setDirty(false);
  }, [config]);

  const defaultProfile = useMemo(
    () =>
      (form.llm_profiles || []).find(
        (profile) => profile.id === form.default_llm_profile_id
      ) || form.llm_profiles?.[0],
    [form.default_llm_profile_id, form.llm_profiles]
  );

  const update = (key: keyof SystemConfig, value: any) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setDirty(true);
  };

  const updateProfile = (profileId: string, patch: Partial<LlmProfile>) => {
    setForm((prev) => ({
      ...prev,
      llm_profiles: (prev.llm_profiles || []).map((profile) =>
        profile.id === profileId ? { ...profile, ...patch } : profile
      ),
    }));
    setDirty(true);
  };

  const addProfile = () => {
    const next = createEmptyProfile();
    setForm((prev) => ({
      ...prev,
      llm_profiles: [...(prev.llm_profiles || []), next],
      default_llm_profile_id:
        prev.default_llm_profile_id || next.id,
    }));
    setDirty(true);
  };

  const removeProfile = (profileId: string) => {
    setForm((prev) => {
      const profiles = (prev.llm_profiles || []).filter((profile) => profile.id !== profileId);
      return {
        ...prev,
        llm_profiles: profiles,
        default_llm_profile_id:
          prev.default_llm_profile_id === profileId ? profiles[0]?.id || '' : prev.default_llm_profile_id,
      };
    });
    setDirty(true);
  };

  const setDefaultProfile = (profileId: string) => {
    update('default_llm_profile_id', profileId);
  };

  const validateProfiles = () => {
    if (!(form.llm_profiles || []).length) {
      toast.error('请至少配置一个模型');
      return false;
    }
    for (const profile of form.llm_profiles || []) {
      if (!profile.name.trim() || !profile.base_url.trim() || !profile.model.trim()) {
        toast.error('每个模型都需要填写名称、API 地址和模型名');
        return false;
      }
    }
    const normalizedIds = normalizeProfiles(form.llm_profiles || []).map((profile) => profile.id);
    if (new Set(normalizedIds).size !== normalizedIds.length) {
      toast.error('模型配置名称/ID 发生冲突，请修改后再保存');
      return false;
    }
    return true;
  };

  const normalizeProfiles = (profiles: LlmProfile[]) =>
    profiles.map((profile) => ({
      ...profile,
      id: slugify(profile.id || profile.name || profile.model),
      name: profile.name.trim(),
      base_url: profile.base_url.trim(),
      model: profile.model.trim(),
      api_key: profile.api_key || '',
      description: profile.description?.trim() || '',
    }));

  const handleSave = async () => {
    if (!validateProfiles()) return;
    setSaving(true);
    try {
      const llm_profiles = normalizeProfiles(form.llm_profiles || []);
      const default_llm_profile_id =
        llm_profiles.find((profile) => profile.id === form.default_llm_profile_id)?.id ||
        llm_profiles[0]?.id ||
        '';
      const updated = await updateSystemConfig({
        ...form,
        llm_profiles,
        default_llm_profile_id,
      });
      onConfigUpdated(updated);
      setDirty(false);
      toast.success('系统设置已保存');
    } catch (err: any) {
      toast.error(err?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setForm({ ...config, llm_profiles: config.llm_profiles || [] });
    setDirty(false);
  };

  const handleTestProfile = async (profile: LlmProfile) => {
    if (!profile.base_url || !profile.model) {
      toast.error('请先填写该模型的 API 地址和模型名称');
      return;
    }
    setTestingProfileId(profile.id);
    setProfileTestResults((prev) => ({ ...prev, [profile.id]: null }));
    try {
      const result = await testLlmConnection({
        base_url: profile.base_url,
        model: profile.model,
        api_key: profile.api_key || '',
      });
      setProfileTestResults((prev) => ({ ...prev, [profile.id]: result }));
      if (result.success) {
        toast.success(`模型连接成功${result.latency_ms ? `（${result.latency_ms}ms）` : ''}`);
      } else {
        toast.error('连接失败：' + result.message);
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '连接测试失败';
      setProfileTestResults((prev) => ({
        ...prev,
        [profile.id]: { success: false, message: msg },
      }));
      toast.error(msg);
    } finally {
      setTestingProfileId(null);
    }
  };

  const handleTestEmbeddingConnection = async () => {
    if (!form.embedding_base_url || !form.embedding_model) {
      toast.error('请先填写向量化 API 地址和模型名称');
      return;
    }
    setTestingEmbedding(true);
    setEmbeddingTestResult(null);
    try {
      const result = await testLlmConnection({
        base_url: form.embedding_base_url,
        model: form.embedding_model,
        api_key: form.embedding_api_key || defaultProfile?.api_key || '',
        endpoint_type: 'embedding',
      });
      setEmbeddingTestResult(result);
      if (result.success) {
        toast.success(
          `向量化模型连接成功${result.latency_ms ? `（${result.latency_ms}ms）` : ''}`
        );
      } else {
        toast.error('向量化连接失败：' + result.message);
      }
    } catch (err: any) {
      const msg = err?.response?.data?.detail || '向量化连接测试失败';
      setEmbeddingTestResult({ success: false, message: msg });
      toast.error(msg);
    } finally {
      setTestingEmbedding(false);
    }
  };

  const TestResultPill: React.FC<{ result: TestResult | null }> = ({ result }) => {
    if (!result) return null;
    return (
      <span
        className={[
          'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11.5px]',
          result.success
            ? 'border-success/30 bg-success-soft text-success'
            : 'border-danger/30 bg-danger-soft text-danger',
        ].join(' ')}
      >
        {result.success ? <Wifi size={11} /> : <WifiOff size={11} />}
        {result.success
          ? `连接正常${result.latency_ms ? ` · ${result.latency_ms}ms` : ''}`
          : result.message}
      </span>
    );
  };

  const ToggleRow: React.FC<{
    label: string;
    description: string;
    value: boolean;
    field: keyof SystemConfig;
    warning?: string;
  }> = ({ label, description, value, field, warning }) => (
    <div className="flex items-start justify-between gap-4 border-b border-line-subtle py-4 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="text-[13.5px] font-medium text-ink-1">{label}</p>
        <p className="mt-0.5 text-[12px] text-ink-3">{description}</p>
        {warning && value && (
          <div className="mt-2 flex items-center gap-1.5 text-[11.5px] text-warning">
            <AlertTriangle size={12} />
            <span>{warning}</span>
          </div>
        )}
      </div>
      <Switch checked={value} onChange={(v) => update(field, v)} />
    </div>
  );

  return (
    <div className="max-w-4xl space-y-6">
      <div className="ds-card p-5">
        <CardHeader
          icon={<Bot size={16} />}
          title="模型池配置"
          description="在这里统一配置多个可复用模型，员工页只需选择其中一个"
        />

        <div className="mt-4 space-y-4">
          {(form.llm_profiles || []).map((profile, index) => {
            const isDefault = profile.id === form.default_llm_profile_id;
            return (
              <div key={profile.id} className="rounded-xl border border-line-subtle bg-surface p-4">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="text-[13px] font-medium text-ink-1">模型 {index + 1}</span>
                    {isDefault && (
                      <span className="inline-flex items-center gap-1 rounded-full border border-brand/30 bg-brand/10 px-2 py-0.5 text-[11px] text-brand">
                        <CheckCircle2 size={11} />
                        系统默认
                      </span>
                    )}
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setDefaultProfile(profile.id)}
                      disabled={isDefault}
                    >
                      设为默认
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      loading={testingProfileId === profile.id}
                      onClick={() => handleTestProfile(profile)}
                      leftIcon={testingProfileId !== profile.id ? <Wifi size={13} /> : undefined}
                    >
                      {testingProfileId === profile.id ? '测试中…' : '测试连接'}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => removeProfile(profile.id)}
                      leftIcon={<Trash2 size={13} />}
                      disabled={(form.llm_profiles || []).length <= 1}
                    >
                      删除
                    </Button>
                  </div>
                </div>

                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  <Input
                    label="模型别名"
                    placeholder="如：OpenAI 主模型 / 内网推理模型"
                    value={profile.name}
                    onChange={(e) => updateProfile(profile.id, { name: e.target.value })}
                  />
                  <Input
                    label="模型 ID"
                    placeholder="如：gpt-4o / qwen-max"
                    className="font-mono"
                    value={profile.model}
                    onChange={(e) => updateProfile(profile.id, { model: e.target.value })}
                  />
                  <Input
                    label="API 基础地址"
                    placeholder="https://api.openai.com/v1"
                    value={profile.base_url}
                    onChange={(e) => updateProfile(profile.id, { base_url: e.target.value })}
                  />
                  <Input
                    label="说明（可选）"
                    placeholder="例如：成本更低，适合资料抽取"
                    value={profile.description || ''}
                    onChange={(e) => updateProfile(profile.id, { description: e.target.value })}
                  />
                </div>

                <div className="mt-4">
                  <Input
                    label="API 密钥"
                    type={showApiKey ? 'text' : 'password'}
                    className="font-mono"
                    placeholder="sk-..."
                    value={profile.api_key || ''}
                    onChange={(e) => updateProfile(profile.id, { api_key: e.target.value })}
                    rightAddon={
                      <button
                        type="button"
                        onClick={() => setShowApiKey(!showApiKey)}
                        className="pointer-events-auto rounded p-1 text-ink-3 hover:text-ink-1"
                        aria-label="切换显示"
                      >
                        {showApiKey ? <EyeOff size={14} /> : <Eye size={14} />}
                      </button>
                    }
                  />
                </div>

                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <TestResultPill result={profileTestResults[profile.id] || null} />
                </div>
              </div>
            );
          })}

          <Button
            variant="outline"
            size="md"
            leftIcon={<Plus size={14} />}
            onClick={addProfile}
          >
            新增模型配置
          </Button>
        </div>
      </div>

      <div className="ds-card p-5">
        <CardHeader
          icon={<Database size={16} />}
          title="知识库与向量化配置"
          description="管理任务证据索引的构建与检索行为"
        />

        <div className="mt-4 space-y-4">
          <div className="flex items-start justify-between gap-4 border-b border-line-subtle pb-4">
            <div>
              <p className="text-[13.5px] font-medium text-ink-1">启用向量化证据索引</p>
              <p className="mt-0.5 text-[12px] leading-relaxed text-ink-3">
                上传文件会先构建任务知识库；启用后额外调用向量化模型生成片段 embedding。
              </p>
            </div>
            <Switch
              checked={form.vector_store_enabled}
              onChange={(v) => update('vector_store_enabled', v)}
            />
          </div>

          <Input
            label="向量化 API 基础地址"
            placeholder="https://api.openai.com/v1"
            value={form.embedding_base_url || ''}
            onChange={(e) => update('embedding_base_url', e.target.value)}
          />

          <Input
            label="向量化模型"
            placeholder="text-embedding-3-small"
            value={form.embedding_model || ''}
            onChange={(e) => update('embedding_model', e.target.value)}
          />

          <Input
            label="向量化 API 密钥"
            type={showApiKey ? 'text' : 'password'}
            className="font-mono"
            placeholder="留空则使用系统默认模型的 API 密钥"
            value={form.embedding_api_key || ''}
            onChange={(e) => update('embedding_api_key', e.target.value)}
          />

          <div className="grid grid-cols-2 gap-4">
            <Input
              label="知识片段长度"
              type="number"
              min={400}
              max={4000}
              value={form.kb_chunk_size || 1200}
              onChange={(e) => update('kb_chunk_size', parseInt(e.target.value) || 1200)}
            />
            <Input
              label="证据片段 Top K"
              type="number"
              min={4}
              max={40}
              value={form.kb_top_k || 12}
              onChange={(e) => update('kb_top_k', parseInt(e.target.value) || 12)}
            />
          </div>

          <div className="flex flex-wrap items-center gap-3 pt-1">
            <Button
              variant="outline"
              size="sm"
              onClick={handleTestEmbeddingConnection}
              loading={testingEmbedding}
              leftIcon={!testingEmbedding ? <Wifi size={13} className="text-cedar" /> : undefined}
            >
              {testingEmbedding ? '测试中…' : '测试向量化'}
            </Button>
            <TestResultPill result={embeddingTestResult} />
          </div>
        </div>
      </div>

      <div className="ds-card p-5">
        <CardHeader
          icon={<Zap size={16} />}
          title="功能开关"
          description="控制智能体的外部能力"
        />
        <div className="mt-2">
          <ToggleRow
            label="联网搜索"
            description="允许智能体通过互联网搜索获取最新信息"
            value={form.enable_external_search}
            field="enable_external_search"
            warning="启用联网搜索将访问外部网络，请确保网络策略允许"
          />
          <ToggleRow
            label="浏览器控制"
            description="允许智能体控制浏览器进行网页操作和截图"
            value={form.enable_browser}
            field="enable_browser"
            warning="浏览器控制需要服务器端安装 Playwright 依赖"
          />
        </div>
      </div>

      <div className="ds-card p-5">
        <CardHeader
          icon={<SlidersHorizontal size={16} />}
          title="性能参数"
          description="调整沙箱与并行执行的资源配额"
        />

        <div className="mt-4 grid grid-cols-2 gap-4">
          <Input
            label="沙箱超时时间（秒）"
            type="number"
            min={10}
            max={600}
            value={form.sandbox_timeout}
            onChange={(e) => update('sandbox_timeout', parseInt(e.target.value) || 30)}
            hint="推荐：30 – 120 秒"
          />
          <Input
            label="最大并行工作数"
            type="number"
            min={1}
            max={20}
            value={form.max_workers}
            onChange={(e) => update('max_workers', parseInt(e.target.value) || 4)}
            hint="推荐：2 – 8 个"
          />
        </div>
      </div>

      <div className="sticky bottom-4 z-10 flex flex-wrap items-center gap-3 rounded-xl border border-line-subtle bg-elevated/90 p-3 shadow-card backdrop-blur">
        <Button
          variant="primary"
          size="md"
          onClick={handleSave}
          disabled={!dirty}
          loading={saving}
          leftIcon={!saving ? <Save size={14} /> : undefined}
        >
          {saving ? '保存中…' : '保存设置'}
        </Button>
        {dirty && (
          <Button
            variant="outline"
            size="md"
            leftIcon={<RefreshCw size={13} />}
            onClick={handleReset}
          >
            撤销修改
          </Button>
        )}
        {dirty && (
          <span className="inline-flex items-center gap-1.5 text-[12px] text-warning">
            <AlertTriangle size={12} />
            有未保存的更改
          </span>
        )}
      </div>
    </div>
  );
};

export default SystemSettings;
