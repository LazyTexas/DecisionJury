// ============================================================
// 认证 API（登录 / 注册）
// 后端契约（扁平格式，无 token）：
//   POST /api/auth/register  body {user_id, name, password}
//   POST /api/auth/login     body {user_id, password}
//   成功返回 {success:true, user_id, name}
//   失败返回 success:false + message（兼容扁平与信封两种形态）
// 说明：若后端 auth 路由未挂 /api 前缀（实际为 /auth/...），
//       将下面 AUTH_BASE 改为 '/auth' 即可。
// ============================================================

import type { AuthUser } from '../types';
import { ApiRequestError, isMockMode } from './index';
import { translateApiError } from '../utils/errors';

const AUTH_BASE = '/api/auth';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

interface AuthHttpBody {
  success?: boolean;
  message?: string;
  user_id?: string;
  name?: string;
  data?: { user_id?: string; name?: string } | null;
}

async function postAuth<T extends AuthHttpBody>(path: string, payload: Record<string, string>): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${AUTH_BASE}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
  } catch {
    throw new ApiRequestError('网络连接失败，请确认后端服务已启动');
  }

  let body: AuthHttpBody | null = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const code = typeof body?.message === 'string' ? body.message : undefined;
    throw new ApiRequestError(translateApiError(code, `请求失败（HTTP ${res.status}）`), code, res.status);
  }

  // 失败：扁平 {success:false, message} 或信封 {success:false, data:null, message}
  if (body && body.success === false) {
    const code = typeof body.message === 'string' ? body.message : undefined;
    throw new ApiRequestError(translateApiError(code), code);
  }

  return body as T;
}

function toAuthUser(body: AuthHttpBody): AuthUser {
  // 兼容：扁平 {user_id, name} 或信封 {data:{user_id,name}}
  const data = body.data ?? body;
  if (!data?.user_id) throw new ApiRequestError('登录响应缺少 user_id，请与后端确认契约');
  return { user_id: data.user_id, name: data.name ?? data.user_id };
}

/** 注册（成功即视为可登录，返回用户身份） */
export async function registerUser(req: {
  user_id: string; name: string; password: string;
}): Promise<AuthUser> {
  if (isMockMode) {
    await sleep(400);
    return { user_id: req.user_id, name: req.name || req.user_id };
  }
  const body = await postAuth('/register', req);
  return toAuthUser(body);
}

/** 登录，成功返回用户身份 */
export async function loginUser(req: {
  user_id: string; password: string;
}): Promise<AuthUser> {
  if (isMockMode) {
    await sleep(400);
    return { user_id: req.user_id, name: '演示用户' };
  }
  const body = await postAuth('/login', req);
  return toAuthUser(body);
}
