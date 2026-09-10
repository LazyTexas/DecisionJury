// ============================================================
// AuthContext：登录态状态层
// 登录态 = localStorage 存了 {user_id, name} + JWT access_token（key='token'）。
// 刷新页面时同步从 localStorage 恢复（无异步请求，不闪登录页）。
// 业务接口在 api/index.ts 的 request() 里自动注入 Authorization: Bearer <token>。
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
  saveStoredToken, clearStoredToken, getStoredToken,
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

/**
 * 初始化登录态：mock 自动登录；真实模式从 localStorage 恢复。
 *
 * 关键：登录态必须「用户身份 + JWT」齐备。
 * 引入 JWT 之前登录的老会话只有 dj:auth、没有 token，此时若视为已登录，
 * 会出现「页面能打开、但所有接口都返回 MISSING_USER_ID」的假死状态；
 * 因此这里把这种不完整会话判为未登录并清理，避免后续误判与重定向死循环。
 */
function initialUser(): AuthUser | null {
  if (isMockMode) return DEMO_USER;
  const stored = loadStoredUser();
  if (stored && !getStoredToken()) {
    clearStoredUser();
    return null;
  }
  return stored;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(initialUser);

  const login = useCallback(async (user_id: string, password: string) => {
    const result = await loginUser({ user_id, password });
    // 先落 token，再落用户身份，确保后续业务请求能立刻带上 Authorization
    if (result.token) saveStoredToken(result.token);
    saveStoredUser(result.user);
    setUser(result.user);
  }, []);

  const register = useCallback(async (user_id: string, name: string, password: string) => {
    const authUser = await registerUser({ user_id, name, password });
    // 注册接口不返回 token：注册成功后补一次登录以取得 access_token，
    // 保证后端开启强制 JWT（ENFORCE_JWT=true）时注册后也能立刻正常访问业务接口。
    // 补登录失败不阻断注册本身（兼容模式下仍可凭 user_id 工作）。
    try {
      const result = await loginUser({ user_id, password });
      if (result.token) saveStoredToken(result.token);
      saveStoredUser(result.user);
      setUser(result.user);
    } catch {
      saveStoredUser(authUser);
      setUser(authUser);
    }
  }, []);

  const logout = useCallback(() => {
    clearStoredToken();
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
