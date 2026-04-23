import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Eye, EyeOff, ShieldCheck, Sparkles, Workflow } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/auth';
import { setAuthToken } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import { Button, Input, BrandMark } from '../components/ui';
import toast from 'react-hot-toast';
import { getApiErrorMessage } from '../utils/errors';

const HIGHLIGHTS = [
  {
    icon: Workflow,
    title: '主管编排的多智能体',
    desc: '资料、研究、数据、图表、报告、质检六类数字员工协同工作。',
  },
  {
    icon: ShieldCheck,
    title: '证据可追溯报告',
    desc: '所有结论链接到原始 evidence，而非凭空生成的话术。',
  },
  {
    icon: Sparkles,
    title: '企业级交付',
    desc: '支持 Word / PPT / 数据表模板化输出，贴合企业规范。',
  },
];

export const LoginPage: React.FC = () => {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const { login: storeLogin } = useAuthStore();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username || !password) {
      toast.error('请输入用户名和密码');
      return;
    }

    setLoading(true);
    try {
      const response = await login({ username, password });
      setAuthToken(response.access_token);
      storeLogin(response.user, response.access_token);
      toast.success(`欢迎回来，${response.user.username}`);
      navigate('/');
    } catch (err: any) {
      const msg =
        err?.response?.status === 401
          ? '用户名或密码错误'
          : getApiErrorMessage(err, '登录失败，请重试');
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen overflow-hidden bg-paper">
      {/* Soft paper grain backdrop */}
      <div className="pointer-events-none absolute inset-0 opacity-[0.35] [mask-image:radial-gradient(ellipse_at_center,black,transparent_70%)] bg-paper-grain" />

      <div className="relative mx-auto grid min-h-screen max-w-6xl grid-cols-1 gap-10 px-6 py-14 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:py-0">
        {/* ── Left: brand story ───────────────────────────────── */}
        <section className="hidden flex-col justify-center gap-10 lg:flex">
          <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex items-center gap-3"
          >
            <BrandMark size={44} />
            <div>
              <p className="font-serif text-[18px] font-semibold tracking-tight text-ink-1">
                深度研究数据分析智能体
              </p>
              <p className="text-caption uppercase tracking-[0.24em] text-ink-3">
                dataagent · Data Analysis Agent
              </p>
            </div>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
            className="space-y-5"
          >
            <span className="ds-eyebrow">企业数据分析与报告平台</span>
            <h1 className="text-display font-semibold leading-[1.15] tracking-tight text-ink-1 text-balance">
              把材料、数据与主管智能体
              <br />
              编排成可交付的正式报告
            </h1>
            <p className="max-w-lg text-lead text-ink-2 leading-relaxed text-pretty">
              从上传文档开始，系统自动建立证据索引、规划工作流，再由主管调度数字员工完成分析、图表、撰写与质检，输出可追溯的 Word / PPT 报告。
            </p>
          </motion.div>

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.2 }}
            className="grid gap-3 sm:grid-cols-3"
          >
            {HIGHLIGHTS.map(({ icon: Icon, title, desc }) => (
              <div
                key={title}
                className="ds-card p-4 transition-shadow hover:shadow-card"
              >
                <Icon size={20} className="text-brand" />
                <p className="mt-3 text-[13.5px] font-semibold text-ink-1">{title}</p>
                <p className="mt-1 text-small text-ink-3 leading-relaxed">{desc}</p>
              </div>
            ))}
          </motion.div>
        </section>

        {/* ── Right: login card ───────────────────────────────── */}
        <section className="flex items-center justify-center">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.2, 0, 0, 1] }}
            className="w-full max-w-[420px]"
          >
            <div className="mb-6 flex items-center gap-3 lg:hidden">
              <BrandMark size={40} />
              <div>
                <p className="font-serif text-[16px] font-semibold text-ink-1">深度研究数据分析智能体</p>
                <p className="text-caption uppercase tracking-[0.22em] text-ink-3">
                  dataagent
                </p>
              </div>
            </div>

            <div className="overflow-hidden rounded-2xl border border-line-subtle bg-elevated shadow-card">
              <div className="h-[3px] bg-gradient-to-r from-brand via-gold to-cedar" />
              <div className="px-8 py-8 sm:px-9 sm:py-10">
                <div className="mb-7">
                  <h2 className="text-h2 font-semibold text-ink-1">登录账户</h2>
                  <p className="mt-1.5 text-small text-ink-3">
                    使用你的账户继续研究与报告任务
                  </p>
                </div>

                <form onSubmit={handleSubmit} className="space-y-4">
                  <Input
                    label="用户名"
                    name="username"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    placeholder="请输入用户名"
                    autoComplete="username"
                    autoFocus
                  />
                  <Input
                    label="密码"
                    name="password"
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="请输入密码"
                    autoComplete="current-password"
                    rightAddon={
                      <button
                        type="button"
                        onClick={() => setShowPassword((v) => !v)}
                        className="flex h-8 w-8 items-center justify-center rounded-md text-ink-3 hover:text-ink-1"
                        aria-label={showPassword ? '隐藏密码' : '显示密码'}
                      >
                        {showPassword ? <EyeOff size={15} /> : <Eye size={15} />}
                      </button>
                    }
                  />
                  <Button
                    type="submit"
                    size="lg"
                    loading={loading}
                    fullWidth
                    className="mt-2"
                  >
                    {loading ? '登录中...' : '登录'}
                  </Button>
                </form>
              </div>
            </div>

            <p className="mt-6 text-center text-caption text-ink-3">
              深度研究数据分析智能体 · dataagent · 企业内部系统
            </p>
          </motion.div>
        </section>
      </div>
    </div>
  );
};

export default LoginPage;
