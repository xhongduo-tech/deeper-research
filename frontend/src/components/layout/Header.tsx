import React from 'react';
import { Moon, Sun } from 'lucide-react';
import { useAuthStore } from '../../stores/authStore';
import { useUiStore } from '../../stores/uiStore';

export const Header: React.FC = () => {
  const { isAuthenticated, user } = useAuthStore();
  const { theme, toggleTheme } = useUiStore();

  return (
    <header className="relative z-10 flex h-14 flex-shrink-0 items-center gap-4 border-b border-line-subtle bg-surface/60 px-5 backdrop-blur-[2px]">
      <div className="flex min-w-0 flex-1 items-center gap-3">
        <span className="hidden text-caption uppercase tracking-[0.18em] text-ink-3 sm:inline">
          dataagent · 报告生产台
        </span>
        <span className="hidden h-3 w-px bg-line sm:inline" />
        <span className="text-[13px] text-ink-2">
          深度研究数据分析智能体 · 主管主持的多员工报告生产系统
        </span>
      </div>

      <button
        type="button"
        onClick={toggleTheme}
        aria-label="切换深浅模式"
        title="切换深浅模式"
        className="flex h-8 w-8 items-center justify-center rounded-md text-ink-3 transition-colors hover:bg-sunken hover:text-ink-1"
      >
        {theme === 'dark' ? <Sun size={15} /> : <Moon size={15} />}
      </button>

      {isAuthenticated && user?.username && (
        <div className="hidden items-center gap-2 lg:flex" aria-hidden>
          <span className="text-caption text-ink-3">
            {user.role === 'admin' ? '管理员' : '当前用户'}
          </span>
          <span className="text-[13px] font-medium text-ink-1">
            {user.username}
          </span>
        </div>
      )}
    </header>
  );
};

export default Header;
