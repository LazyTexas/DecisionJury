// ============================================================
// AuthContext：登录态状态层
// 后端 auth 契约无 token：登录态 = localStorage 存了 {user_id, name}。
// 刷新页面时同步从 localStorage 恢复（无异步请求，不闪登录页）。
// mock 模式（VITE_USE_MOCK=true）：首次进入自动以演示用户身份登录，
// 登出后停留在登录页（可预览登录/注册表单），刷新即恢复演示用户。
// ============================================================

import { createContext, useCallback, useContext, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import type { AuthUser } from '../types';
import { isMockMode, MOCK_USER_ID } from '../api';
import { registerUser, loginUser } from '../api/auth';
import {
  loadStoredUser, saveStoredUser, clearStoredUser,
} from './storage';

const DEMO_USER: AuthUser = { user_id: MOCK_USER_ID, name: '演示用户' };

interface AuthContextValue {
  /** 当前登录用户；null 表示未登录 */
  user: AuthUser | null;
  login: (user_id: string, password: string) => Promise<void>;
  register: (user_id: string, name: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/** 初始化登录态：mock 自动登录；真实模式从 localStorage 恢复 */
function initialUser(): AuthUser | null {
  if (isMockMode) return DEMO_USER;
  return loadStoredUser();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(initialUser);

  const login = useCallback(async (user_id: string, password: string) => {
    const authUser = await loginUser({ user_id, password });
    saveStoredUser(authUser);
    setUser(authUser);
  }, []);

  const register = useCallback(async (user_id: string, name: string, password: string) => {
    const authUser = await registerUser({ user_id, name, password });
    // 注册成功即视为已登录（后端返回了用户身份）
    saveStoredUser(authUser);
    setUser(authUser);
  }, []);

  const logout = useCallback(() => {
    clearStoredUser();
    setUser(null);
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, login, register, logout }),
    [user, login, register, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth 必须在 <AuthProvider> 内使用');
  return ctx;
}
