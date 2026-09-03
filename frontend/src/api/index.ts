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
import { getStoredUserId } from '../auth/storage';
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

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE_URL}${url}`, {
      headers: { 'Content-Type': 'application/json' },
      ...options,
    });
  } catch {
    // 网络层失败（后端未启动 / 代理断开）
    throw new ApiRequestError('网络连接失败，请确认后端服务已启动（localhost:8000）');
  }

  let body: { success?: boolean; data?: unknown; message?: string } | null = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }

  if (!res.ok) {
    const code = typeof body?.message === 'string' ? body.message : undefined;
    throw new ApiRequestError(
      translateApiError(code, `请求失败（HTTP ${res.status}）`),
      code,
      res.status,
    );
  }

  if (body && body.success === false) {
    const code = typeof body.message === 'string' ? body.message : undefined;
    throw new ApiRequestError(translateApiError(code), code);
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
  try {
    const raw = await request<Record<string, unknown>>(`/cases/${caseId}`);
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
  } catch {
    return null;
  }
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
  return request(`/cases/${caseId}/debate`, { method: 'POST' });
}

export async function getTrace(caseId: string): Promise<{ case_id: string; trace: TraceItem[] }> {
  if (USE_MOCK) return mockFetchTrace(caseId);
  return request(`/cases/${caseId}/trace`);
}

// ---- 判决书 API ----

export async function getReport(caseId: string): Promise<DecisionReport | null> {
  if (USE_MOCK) return mockFetchReport(caseId);
  try {
    const raw = await request<Record<string, unknown>>(`/cases/${caseId}/report`);
    if (!raw) return null;
    return { ...raw, case_id: (raw.case_id as string) ?? caseId } as DecisionReport;
  } catch {
    return null;
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
