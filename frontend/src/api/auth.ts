// ============================================================
// 认证 API（登录 / 注册）
// 后端契约（与业务接口前缀不同，auth 无 /api 前缀）：
//   POST /auth/register  body {user_id, name, password}
//   POST /auth/login     body {user_id, password}
//   登录成功返回信封 {success:true, data:{user_id, name, access_token, token_type}, message}
//   注册成功返回 {success:true, data:{user_id, name}, message}（不含 token）
//   失败返回 {success:false, data:null, message:"用户已存在"/"用户不存在"/"密码错误"}（HTTP 200）
// 说明：登录成功后由上层把 access_token 存入 localStorage（key='token'），
//       业务接口统一在 api/index.ts 的 request() 里注入 Authorization: Bearer <token>。
//       user_id 仍按原契约随请求传递，JWT 作为身份校验的补充。
// ============================================================

import type { AuthUser } from '../types';
import { ApiRequestError, isMockMode } from './index';
import { translateApiError } from '../utils/errors';

// 后端 auth router prefix="/auth"（无 /api），需经 vite 代理 '/auth' 转发
const AUTH_BASE = '/auth';

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

interface AuthHttpBody {
  success?: boolean;
  message?: string;
  user_id?: string;
  name?: string;
  access_token?: string;
  token_type?: string;
  data?: { user_id?: string; name?: string; access_token?: string; token_type?: string } | null;
}

/** 登录结果：用户身份 + JWT */
export interface LoginResult {
  user: AuthUser;
  token: string | null;
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

/** 从响应里取 access_token（兼容信封 / 扁平两种形态） */
function toAccessToken(body: AuthHttpBody): string | null {
  const data = body.data ?? body;
  const token = data?.access_token;
  return typeof token === 'string' && token ? token : null;
}

/** 注册（成功即视为可登录，返回用户身份；注册接口不返回 token） */
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

/** 登录，成功返回用户身份与 JWT access_token */
export async function loginUser(req: {
  user_id: string; password: string;
}): Promise<LoginResult> {
  if (isMockMode) {
    await sleep(400);
    return { user: { user_id: req.user_id, name: '演示用户' }, token: null };
  }
  const body = await postAuth('/login', req);
  return { user: toAuthUser(body), token: toAccessToken(body) };
}
