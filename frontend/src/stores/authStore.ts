import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import type { User } from '../types';
import { TOKEN_KEY } from '../utils/constants';

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  /** 登录弹窗是否打开 */
  loginModalOpen: boolean;
  /** 登录成功后的回调（用于「需要登录才能继续」场景） */
  loginSuccessCallback: (() => void) | null;
  setUser: (user: User) => void;
  setToken: (token: string) => void;
  login: (user: User, token: string) => void;
  logout: () => void;
  openLoginModal: (onSuccess?: () => void) => void;
  closeLoginModal: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      loginModalOpen: false,
      loginSuccessCallback: null,

      setUser: (user) => set({ user, isAuthenticated: true }),
      setToken: (token) => {
        localStorage.setItem(TOKEN_KEY, token);
        set({ token });
      },

      login: (user, token) => {
        localStorage.setItem(TOKEN_KEY, token);
        set({ user, token, isAuthenticated: true });
      },

      logout: () => {
        localStorage.removeItem(TOKEN_KEY);
        set({ user: null, token: null, isAuthenticated: false });
      },

      openLoginModal: (onSuccess) =>
        set({ loginModalOpen: true, loginSuccessCallback: onSuccess ?? null }),

      closeLoginModal: () =>
        set({ loginModalOpen: false, loginSuccessCallback: null }),
    }),
    {
      name: 'auth-store',
      partialize: (state) => ({
        user: state.user,
        token: state.token,
        isAuthenticated: state.isAuthenticated,
        // 弹窗状态不持久化
      }),
    }
  )
);
