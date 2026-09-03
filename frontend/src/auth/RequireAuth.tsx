// ============================================================
// 路由守卫：未登录访问受保护页面 → 重定向 /login，并记住来源
// 登录成功后由登录页跳回原目标页。
// ============================================================

import { Navigate, useLocation } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useAuth } from './AuthContext';

export default function RequireAuth({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const location = useLocation();

  if (!user) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  return <>{children}</>;
}
