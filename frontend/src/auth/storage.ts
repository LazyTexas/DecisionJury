// ============================================================
// 登录态本地存储（单一来源）
// 后端 auth 契约无 token：登录态 = localStorage 里存了 {user_id, name}。
// api 层与 AuthContext 都从这里读写，保证一致。
// ============================================================

import type { AuthUser } from '../types';

export const AUTH_STORAGE_KEY = 'dj:auth';

export function loadStoredUser(): AuthUser | null {
  try {
    const raw = localStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed && typeof parsed.user_id === 'string' && parsed.user_id) {
      return { user_id: parsed.user_id, name: parsed.name ?? parsed.user_id };
    }
    return null;
  } catch {
    return null;
  }
}

export function saveStoredUser(user: AuthUser): void {
  try {
    localStorage.setItem(AUTH_STORAGE_KEY, JSON.stringify(user));
  } catch {
    // 隐私模式 / 存储满：静默失败，本次会话内仍可用
  }
}

export function clearStoredUser(): void {
  try {
    localStorage.removeItem(AUTH_STORAGE_KEY);
  } catch {
    /* ignore */
  }
}

/** 供 api 层同步读取当前 user_id（未登录返回 null） */
export function getStoredUserId(): string | null {
  return loadStoredUser()?.user_id ?? null;
}
