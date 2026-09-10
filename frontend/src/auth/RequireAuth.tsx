// ============================================================
// 路由守卫：未登录访问受保护页面 → 重定向 /login，并记住来源
// 登录成功后由登录页跳回原目标页。
//
// 同时校验 JWT：只有 dj:auth（用户）但没有 token 的“老会话”，
// 会进到一个「页面能打开、但所有接口都拿不到数据」的假死状态，
// 因此这里要求两者齐备，缺 token 直接回登录页。
// mock 模式（VITE_USE_MOCK=true）不发真实请求，不要求 token。
// ============================================================

import { useEffect } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuth } from './AuthContext';
import { isMockMode } from '../api';
import { getStoredToken } from './storage';

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const location = useLocation();

  // 有用户身份但缺 token：视为登录态不完整，回登录页重新登录
  const incompleteSession = !isMockMode && !!user && !getStoredToken();

  // 同步清理 React 登录态。否则会与 LoginPage 的「已登录则跳首页」互相弹跳，
  // 形成无限重定向（/ → /login → / → …）。
  useEffect(() => {
    if (incompleteSession) logout();
  }, [incompleteSession, logout]);

  if (!user || incompleteSession) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}
