import React, { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Eye, EyeOff, LogIn, UserPlus, X } from 'lucide-react';
import { login, register } from '../../api/auth';
import { setAuthToken } from '../../api/client';
import { useAuthStore } from '../../stores/authStore';
import { Button, Input, BrandMark } from '../ui';
import toast from 'react-hot-toast';
import { getApiErrorMessage } from '../../utils/errors';

interface LoginModalProps {
  open: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  defaultTab?: 'login' | 'register';
}

export const LoginModal: React.FC<LoginModalProps> = ({
  open,
  onClose,
  onSuccess,
  defaultTab = 'login',
}) => {
  const [tab, setTab] = useState<'login' | 'register'>(defaultTab);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPwd, setShowPwd] = useState(false);
  const [loading, setLoading] = useState(false);
  const { login: storeLogin } = useAuthStore();

  useEffect(() => {
    if (open) {
      setUsername('');
      setPassword('');
      setShowPwd(false);
      setTab(defaultTab);
    }
  }, [open, defaultTab]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    if (open) document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [open, onClose]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!username.trim() || !password) {
      toast.error('请输入用户名和密码');
      return;
    }

    setLoading(true);
    try {
      if (tab === 'login') {
        const res = await login({ username: username.trim(), password });
        setAuthToken(res.access_token);
        storeLogin(res.user, res.access_token);
        toast.success(`欢迎回来，${res.user.username}`);
      } else {
        if (password.length < 6) {
          toast.error('密码至少 6 位');
          setLoading(false);
          return;
        }
        await register({ username: username.trim(), password });
        const res = await login({ username: username.trim(), password });
        setAuthToken(res.access_token);
        storeLogin(res.user, res.access_token);
        toast.success('注册成功，已自动登录');
      }
      onClose();
      onSuccess?.();
    } catch (err: any) {
      const status = err?.response?.status;
      const detail = getApiErrorMessage(err, tab === 'login' ? '登录失败，请重试' : '注册失败，用户名可能已存在');
      if (tab === 'login') {
        toast.error(status === 401 ? '用户名或密码错误' : detail || '登录失败，请重试');
      } else {
        toast.error(detail || '注册失败，用户名可能已存在');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="backdrop"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-veil backdrop-blur-sm"
          onClick={onClose}
        >
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.96, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 16 }}
            transition={{ duration: 0.24, ease: [0.2, 0, 0, 1] }}
            className="relative w-full max-w-md overflow-hidden rounded-2xl border border-line-subtle bg-elevated shadow-pop"
            onClick={(e) => e.stopPropagation()}
            role="dialog"
            aria-modal="true"
          >
            {/* Accent gradient */}
            <div className="h-[3px] bg-gradient-to-r from-brand via-gold to-cedar" />

            <button
              onClick={onClose}
              aria-label="关闭"
              className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-md text-ink-3 transition-colors hover:bg-sunken/60 hover:text-ink-1"
            >
              <X size={16} />
            </button>

            <div className="px-8 py-8">
              {/* Brand */}
              <div className="mb-6 flex items-center gap-3">
                <BrandMark size={38} />
                <div>
                  <h2 className="font-serif text-[16px] font-semibold text-ink-1">
                    深度研究数据分析智能体
                  </h2>
                  <p className="text-caption uppercase tracking-[0.22em] text-ink-3">
                    dataagent
                  </p>
                </div>
              </div>

              {/* Tabs */}
              <div className="mb-5 flex rounded-md bg-sunken/60 p-1">
                {(['login', 'register'] as const).map((t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={[
                      'flex-1 rounded-[7px] py-2 text-[13px] font-medium transition-all',
                      tab === t
                        ? 'bg-elevated text-ink-1 shadow-xs'
                        : 'text-ink-3 hover:text-ink-1',
                    ].join(' ')}
                  >
                    {t === 'login' ? '登录' : '注册'}
                  </button>
                ))}
              </div>

              <form onSubmit={handleSubmit} className="space-y-3.5">
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
                  label={
                    <>
                      密码
                      {tab === 'register' && (
                        <span className="ml-1 text-caption text-ink-4">（至少 6 位）</span>
                      )}
                    </>
                  }
                  name="password"
                  type={showPwd ? 'text' : 'password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder={tab === 'login' ? '请输入密码' : '设置密码'}
                  autoComplete={tab === 'login' ? 'current-password' : 'new-password'}
                  rightAddon={
                    <button
                      type="button"
                      onClick={() => setShowPwd((v) => !v)}
                      className="flex h-8 w-8 items-center justify-center rounded-md text-ink-3 hover:text-ink-1"
                      aria-label={showPwd ? '隐藏密码' : '显示密码'}
                    >
                      {showPwd ? <EyeOff size={14} /> : <Eye size={14} />}
                    </button>
                  }
                />

                <Button
                  type="submit"
                  size="md"
                  loading={loading}
                  fullWidth
                  leftIcon={
                    tab === 'login' ? <LogIn size={15} /> : <UserPlus size={15} />
                  }
                  className="mt-1"
                >
                  {loading
                    ? tab === 'login'
                      ? '登录中...'
                      : '注册中...'
                    : tab === 'login'
                      ? '登录'
                      : '注册账号'}
                </Button>
              </form>

              <p className="mt-5 text-center text-small text-ink-3">
                {tab === 'login' ? '还没有账号？' : '已有账号？'}
                <button
                  onClick={() => setTab(tab === 'login' ? 'register' : 'login')}
                  className="ml-1 text-brand hover:underline"
                >
                  {tab === 'login' ? '立即注册' : '去登录'}
                </button>
              </p>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default LoginModal;
