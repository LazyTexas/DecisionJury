// ============================================================
// API 服务层
// 所有后端接口通过此模块统一导出。
// USE_MOCK = true（或环境变量 VITE_USE_MOCK=true）时使用 Mock 数据。
// 统一约定：业务失败抛 ApiRequestError（message 已翻译为中文）。
// ============================================================

import {
  Case,
  CaseSummary,
  CaseType,
  HistoryItem,
  Message,
  MessageRole,
  SendMessageResponse,
  DecisionReport,
  TraceItem,
  WatchlistItem,
} from '../types';
import { translateApiError } from '../utils/errors';
import { getStoredUserId, getStoredToken, clearStoredToken, clearStoredUser } from '../auth/storage';
import {
  fetchCaseList as mockFetchCaseList,
  fetchCaseDetail as mockFetchCaseDetail,
  createCase as mockCreateCase,
  fetchCaseMessages as mockFetchCaseMessages,
  sendMessage as mockSendMessage,
  startDebate as mockStartDebate,
  fetchReport as mockFetchReport,
  fetchTrace as mockFetchTrace,
  fetchWatchlist as mockFetchWatchlist,
  fetchHistory as mockFetchHistory,
  deleteCase as mockDeleteCase,
} from './mock';

// Mock 开关：开发期可用 VITE_USE_MOCK=true 起 dev server 体验纯前端 demo
const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';
export const isMockMode = USE_MOCK;

/** mock 模式的演示用户（自动登录用，不必落在 localStorage） */
export const MOCK_USER_ID = 'demo_user';

const BASE_URL = '/api';

/** 取当前登录 user_id；未登录时抛错（业务请求应在登录后发起，由路由守卫保证） */
export function getCurrentUserId(): string {
  if (USE_MOCK) return MOCK_USER_ID;
  const uid = getStoredUserId();
  if (!uid) throw new ApiRequestError('登录已失效，请重新登录', 'UNAUTHORIZED');
  return uid;
}

/** 本地缓存命名空间：按用户隔离，避免 A 登录看到 B 的本地历史 */
function cacheNamespace(): string {
  if (USE_MOCK) return MOCK_USER_ID;
  return getStoredUserId() ?? 'anonymous';
}

// ---- 错误类型 ----

export class ApiRequestError extends Error {
  code?: string;
  status?: number;

  constructor(message: string, code?: string, status?: number) {
    super(message);
    this.name = 'ApiRequestError';
    this.code = code;
    this.status = status;
  }
}

/**
 * 从响应体里解析错误码。
 * 后端既可能返回字符串 message（如 "CASE_NOT_FOUND"），
 * 也可能返回 JWT 认证错误的嵌套结构 {message: {code, message}}，
 * 这里统一把两者都归一为 code 字符串。
 */
function extractErrorCode(message: unknown): string | undefined {
  if (typeof message === 'string') return message;
  if (message && typeof message === 'object' && 'code' in message) {
    const code = (message as { code?: unknown }).code;
    if (typeof code === 'string') return code;
  }
  return undefined;
}

/** 从响应体里解析可直接展示的错误文案（嵌套结构取内层 message） */
function extractErrorMessage(message: unknown): string | undefined {
  if (typeof message === 'string') return message;
  if (message && typeof message === 'object' && 'message' in message) {
    const inner = (message as { message?: unknown }).message;
    if (typeof inner === 'string') return inner;
  }
  return undefined;
}

/** token 失效时的统一处理：清本地登录态并回到登录页（防重复跳转） */
function handleUnauthorized(): void {
  clearStoredToken();
  clearStoredUser();
  if (typeof window !== 'undefined') {
    const { pathname } = window.location;
    if (pathname !== '/login' && pathname !== '/register') {
      window.location.replace('/login');
    }
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  // 统一注入 JWT：所有业务请求都经由此处，登录后自动携带 Authorization 头。
  // 注意：先解构出调用方的 headers，再合并，避免 ...options 覆盖掉 Authorization。
  const token = USE_MOCK ? null : getStoredToken();
  const { headers: optionHeaders, ...restOptions } = options ?? {};
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${url}`, {
      ...restOptions,
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(optionHeaders as Record<string, string> | undefined),
      },
    });
  } catch {
    // 网络层失败（后端未启动 / 代理断开）
    throw new ApiRequestError('网络连接失败，请确认后端服务已启动（localhost:8000）');
  }

  // token 缺失 / 无效 / 过期：清登录态并跳登录页
  if (res.status === 401) {
    handleUnauthorized();
    throw new ApiRequestError('登录已失效，请重新登录', 'UNAUTHORIZED', 401);
  }

  let body: { success?: boolean; data?: unknown; message?: unknown } | null = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const code = extractErrorCode(body?.message);
    const readable = extractErrorMessage(body?.message);
    throw new ApiRequestError(
      translateApiError(code ?? readable, `请求失败（HTTP ${res.status}）`),
      code,
      res.status,
    );
  }

  if (body && body.success === false) {
    const code = extractErrorCode(body.message);
    const readable = extractErrorMessage(body.message);
    throw new ApiRequestError(translateApiError(code ?? readable), code);
  }

  // 兼容两种响应形态：{success,data} 信封 或 裸数据
  return (body && 'data' in body ? body.data : body) as T;
}

// ============================================================
// 本地会话缓存（消息历史）
// 后端暂无 GET /api/cases/{id}/messages，前端先用 localStorage
// 按 caseId 缓存消息，刷新页面可恢复。
// TODO(后端配合)：后端补充消息列表接口后，getCaseMessages 切换为服务端拉取。
// ============================================================

const MSG_CACHE_LIMIT = 200;

function msgCacheKey(caseId: string): string {
  return `dj:messages:${cacheNamespace()}:${caseId}`;
}

export function saveLocalMessages(caseId: string, messages: Message[]): void {
  try {
    const slim = messages.slice(-MSG_CACHE_LIMIT);
    localStorage.setItem(msgCacheKey(caseId), JSON.stringify(slim));
  } catch {
    // 隐私模式 / 存储满：静默失败，不阻塞聊天
  }
}

export function loadLocalMessages(caseId: string): Message[] {
  try {
    const raw = localStorage.getItem(msgCacheKey(caseId));
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function clearLocalMessages(caseId: string): void {
  try {
    localStorage.removeItem(msgCacheKey(caseId));
  } catch {
    /* ignore */
  }
}

// ---- 健康检查 ----
export async function healthCheck(): Promise<{ status: string; version: string }> {
  if (USE_MOCK) return { status: 'ok', version: '1.0.0' };
  return request('/health');
}

// ---- 案件 API ----

export async function getCaseList(
  page = 1,
  pageSize = 10,
): Promise<{ items: CaseSummary[]; total: number; page: number; page_size: number }> {
  if (USE_MOCK) {
    const items = await mockFetchCaseList();
    return { items, total: items.length, page, page_size: pageSize };
  }
  return request(`/cases?user_id=${getCurrentUserId()}&page=${page}&page_size=${pageSize}`);
}

export async function getCaseDetail(caseId: string): Promise<Case | null> {
  if (USE_MOCK) return mockFetchCaseDetail(caseId);
  // 与 getCaseList / getHistory / getWatchlist 保持一致：显式携带 user_id。
  // 后端在「无 Token 且无 user_id」时返回 HTTP 200 + {success:false, message:"MISSING_USER_ID"}，
  // 若不带 user_id，老会话会在这里拿不到案件而静默失败。
  // 注意：这里不再吞掉异常——加载失败必须让调用方（页面）能感知并提示，否则页面会假死。
  const raw = await request<Record<string, unknown>>(`/cases/${caseId}?user_id=${getCurrentUserId()}`);
  if (!raw) return null;
  return {
    case_id: raw.case_id as string,
    user_id: raw.user_id as string,
    case_type: raw.case_type as CaseType,
    title: raw.title as string,
    description: raw.description as string,
    status: (raw.case_status ?? raw.status) as Case['status'],
    collected_fields: (raw.collected_fields ?? {}) as Record<string, unknown>,
    missing_fields: (raw.missing_fields ?? []) as string[],
    final_decision: (raw.final_decision ?? null) as string | null,
    report_id: (raw.report_id ?? null) as string | null,
    created_at: raw.created_at as string,
    updated_at: raw.updated_at as string,
  };
}

/** 创建案件；真实后端会返回首个追问 next_question（作为新案件对话首条引导） */
export async function createCase(req: {
  case_type: CaseType; title: string; description: string;
}): Promise<{
  case_id: string; case_status: string;
  collected_fields: Record<string, unknown>; missing_fields: string[];
  next_question: string | null;
}> {
  if (USE_MOCK) {
    const res = await mockCreateCase({ user_id: getCurrentUserId(), ...req });
    return {
      case_id: res.case.case_id,
      case_status: res.case.status,
      collected_fields: {},
      missing_fields: [],
      next_question: res.next_question,
    };
  }
  return request('/cases', {
    method: 'POST',
    body: JSON.stringify({ user_id: getCurrentUserId(), ...req }),
  });
}

export async function updateCase(
  caseId: string,
  data: { title?: string; description?: string; collected_fields?: Record<string, unknown> },
): Promise<Case | null> {
  if (USE_MOCK) return mockFetchCaseDetail(caseId);
  try {
    const raw = await request<Record<string, unknown>>(`/cases/${caseId}`, {
      method: 'PATCH',
      body: JSON.stringify({ user_id: getCurrentUserId(), ...data }),
    });
    return {
      case_id: raw.case_id as string,
      user_id: raw.user_id as string,
      case_type: raw.case_type as CaseType,
      title: raw.title as string,
      description: raw.description as string,
      status: (raw.case_status ?? raw.status) as Case['status'],
      collected_fields: (raw.collected_fields ?? {}) as Record<string, unknown>,
      missing_fields: (raw.missing_fields ?? []) as string[],
      final_decision: (raw.final_decision ?? null) as string | null,
      report_id: (raw.report_id ?? null) as string | null,
      created_at: raw.created_at as string,
      updated_at: raw.updated_at as string,
    };
  } catch {
    return null;
  }
}

// ---- 消息 API ----

export async function sendMessage(
  caseId: string,
  message: string,
): Promise<SendMessageResponse> {
  if (USE_MOCK) {
    const res = await mockSendMessage(caseId, getCurrentUserId(), message);
    return {
      reply: res.reply,
      case_status: res.case_status,
      collected_fields: res.collected_fields,
      missing_fields: res.missing_fields,
    };
  }
  return request(`/cases/${caseId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ user_id: getCurrentUserId(), message }),
  });
}

/**
 * 获取案件对话历史。
 * 后端暂无读取接口：真实模式先读 localStorage 会话缓存（见 saveLocalMessages），
 * 有完整历史后可将本函数切换为 GET /cases/{id}/messages。
 */
export async function getCaseMessages(caseId: string): Promise<Message[]> {
  if (USE_MOCK) return mockFetchCaseMessages(caseId);
  return loadLocalMessages(caseId);
}

/** 追加一条本地助手消息（用于首问引导等非服务端消息）并持久化 */
export function appendLocalAssistantMessage(caseId: string, content: string): Message {
  const msg: Message = {
    message_id: `local_${Date.now()}`,
    case_id: caseId,
    role: MessageRole.ASSISTANT,
    content,
    created_at: new Date().toISOString(),
  };
  saveLocalMessages(caseId, [...loadLocalMessages(caseId), msg]);
  return msg;
}

// ---- Agent 分析 API ----

export async function startDebate(caseId: string): Promise<{
  case_id: string; case_status: string; steps: unknown[];
  rag_evidence: unknown[]; tool_results: unknown[]; report: DecisionReport;
}> {
  if (USE_MOCK) return mockStartDebate(caseId);
  // 后端 start_debate 的入参是必填的 DebateRequest{user_id}，
  // 不发送请求体会被 FastAPI 判为 422（message=VALIDATION_ERROR，页面显示“提交内容有误，请检查后重试”）。
  return request(`/cases/${caseId}/debate`, {
    method: 'POST',
    body: JSON.stringify({ user_id: getCurrentUserId() }),
  });
}

export async function getTrace(caseId: string): Promise<{ case_id: string; trace: TraceItem[] }> {
  if (USE_MOCK) return mockFetchTrace(caseId);
  // 同上：显式携带 user_id，避免无 Token 会话下拿到 MISSING_USER_ID。
  return request(`/cases/${caseId}/trace?user_id=${getCurrentUserId()}`);
}

// ---- 判决书 API ----

export async function getReport(caseId: string): Promise<DecisionReport | null> {
  if (USE_MOCK) return mockFetchReport(caseId);
  try {
    const raw = await request<Record<string, unknown>>(`/cases/${caseId}/report?user_id=${getCurrentUserId()}`);
    if (!raw) return null;
    return { ...raw, case_id: (raw.case_id as string) ?? caseId } as DecisionReport;
  } catch (e) {
    // 「尚未生成判决书」（REPORT_NOT_FOUND）是正常状态，返回 null 交给页面提示；
    // 其余错误（未登录 / 无权限 / 网络）继续抛出，避免被静默吞掉。
    if ((e as ApiRequestError)?.code === 'REPORT_NOT_FOUND') return null;
    throw e;
  }
}

// ---- 历史记录 API ----

export async function getHistory(params?: {
  page?: number; page_size?: number; case_type?: CaseType; result?: string;
}): Promise<{ items: HistoryItem[]; total: number; page: number; page_size: number }> {
  if (USE_MOCK) {
    return mockFetchHistory();
  }
  const query = new URLSearchParams({ user_id: getCurrentUserId() });
  if (params?.page) query.set('page', String(params.page));
  if (params?.page_size) query.set('page_size', String(params.page_size));
  if (params?.case_type) query.set('case_type', params.case_type);
  if (params?.result) query.set('result', params.result);
  return request(`/history?${query.toString()}`);
}

// ---- 复盘 API ----

export async function submitFeedback(
  caseId: string,
  data: { actual_action: string; satisfaction: number; review?: string },
): Promise<{ saved_to_history: boolean; history_id: string }> {
  if (USE_MOCK) {
    return { saved_to_history: true, history_id: `history_mock_${Date.now()}` };
  }
  return request(`/cases/${caseId}/feedback`, {
    method: 'POST',
    body: JSON.stringify({ user_id: getCurrentUserId(), ...data }),
  });
}

// ---- 观察清单 API ----
// 已封装但暂未占 UI（冷静期提醒案件在 delay/reject 后会出现）。
export async function getWatchlist(): Promise<{ items: WatchlistItem[] }> {
  if (USE_MOCK) return mockFetchWatchlist();
  return request(`/watchlist?user_id=${getCurrentUserId()}`);
}

// ---- 案件删除 ----
// TODO(后端配合)：后端待实现 DELETE /api/cases/{case_id}（级联删除案件的消息/轨迹/提醒，
// 并将关联 histories 的 case_id/report_id 置空，保留复盘记录）。
export async function deleteCase(caseId: string): Promise<{ deleted: boolean }> {
  if (USE_MOCK) return mockDeleteCase(caseId);
  return request(`/cases/${caseId}?user_id=${getCurrentUserId()}`, {
    method: 'DELETE',
  });
}

// ---- 历史记录删除（软删）----
export async function deleteHistory(historyId: string): Promise<{ deleted: boolean }> {
  if (USE_MOCK) return { deleted: true };
  return request(`/history/${historyId}?user_id=${getCurrentUserId()}`, { method: 'DELETE' });
}

// ---- 观察清单删除（将提醒标记为已取消）----
export async function deleteWatchlistItem(reminderId: string): Promise<{ deleted: boolean }> {
  if (USE_MOCK) return { deleted: true };
  return request(`/watchlist/${reminderId}?user_id=${getCurrentUserId()}`, { method: 'DELETE' });
}
