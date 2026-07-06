// ============================================================
// API 服务层
// 所有后端接口通过此模块统一导出。
// 路径和字段名与后端 API 文档 04_API.md 对齐。
// USE_MOCK = true 时使用 Mock 数据。
// ============================================================

import {
  Case,
  CaseSummary,
  CaseType,
  CreateCaseResponse,
  Message,
  SendMessageResponse,
  DecisionReport,
  TraceItem,
  HistoryItem,
  WatchlistItem,
} from '../types';
import {
  fetchCaseList as mockFetchCaseList,
  fetchCaseDetail as mockFetchCaseDetail,
  createCase as mockCreateCase,
  fetchCaseMessages as mockFetchCaseMessages,
  sendMessage as mockSendMessage,
  startDebate as mockStartDebate,
  fetchReport as mockFetchReport,
  fetchTrace as mockFetchTrace,
  fetchHistory as mockFetchHistory,
  fetchWatchlist as mockFetchWatchlist,
} from './mock';

const USE_MOCK = true;
const BASE_URL = '/api';

const USER_ID = 'u001'; // MVP 暂定一个用户 ID

// ---- 通用请求工具 ----

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  const body = await res.json();
  if (!body.success) throw new Error(body.message || 'API error');
  return body.data as T;
}

// ---- 健康检查 ----

export async function healthCheck(): Promise<{ status: string; version: string }> {
  if (USE_MOCK) return { status: 'ok', version: '0.2' };
  return request('/health');
}

// ---- 案件 API ----

/** GET /api/cases — 获取案件列表 */
export async function getCaseList(): Promise<CaseSummary[]> {
  if (USE_MOCK) return mockFetchCaseList();
  return request('/cases');
}

/** GET /api/cases/{case_id} — 获取案件详情 */
export async function getCaseDetail(caseId: string): Promise<Case | null> {
  if (USE_MOCK) return mockFetchCaseDetail(caseId);
  return request(`/cases/${caseId}`);
}

/** POST /api/cases — 创建案件 */
export async function createCase(req: {
  case_type: CaseType; title: string; description: string;
}): Promise<CreateCaseResponse> {
  if (USE_MOCK) return mockCreateCase({ user_id: USER_ID, ...req });
  return request('/cases', {
    method: 'POST',
    body: JSON.stringify({ user_id: USER_ID, ...req }),
  });
}

/** PATCH /api/cases/{case_id} — 更新案件字段 */
export async function updateCase(
  caseId: string,
  data: { title?: string; description?: string; collected_fields?: Record<string, unknown> },
): Promise<Case> {
  if (USE_MOCK) return (await mockFetchCaseDetail(caseId))!;
  return request(`/cases/${caseId}`, {
    method: 'PATCH',
    body: JSON.stringify({ user_id: USER_ID, ...data }),
  });
}

// ---- 消息 API ----

/** POST /api/cases/{case_id}/messages — 多轮补充信息 */
export async function sendMessage(
  caseId: string,
  message: string,
): Promise<SendMessageResponse> {
  if (USE_MOCK) {
    const res = await mockSendMessage(caseId, USER_ID, message);
    return {
      reply: res.reply,
      case_status: res.case_status,
      collected_fields: res.collected_fields,
      missing_fields: res.missing_fields,
    };
  }
  return request(`/cases/${caseId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ user_id: USER_ID, message }),
  });
}

/** GET /api/cases/{case_id}/messages — 获取消息列表 */
export async function getCaseMessages(caseId: string): Promise<Message[]> {
  if (USE_MOCK) return mockFetchCaseMessages(caseId);
  return request(`/cases/${caseId}/messages`);
}

// ---- Agent 分析 API ----

/** POST /api/cases/{case_id}/debate — 启动多 Agent 分析 */
export async function startDebate(caseId: string): Promise<{
  case_id: string; case_status: string; steps: any[];
  rag_evidence: any[]; tool_results: any[]; report: DecisionReport;
}> {
  if (USE_MOCK) return mockStartDebate(caseId);
  return request(`/cases/${caseId}/debate`, {
    method: 'POST',
    body: JSON.stringify({ user_id: USER_ID }),
  });
}

/** GET /api/cases/{case_id}/trace — 查询执行轨迹 */
export async function getTrace(caseId: string): Promise<{ case_id: string; trace: TraceItem[] }> {
  if (USE_MOCK) return mockFetchTrace(caseId);
  return request(`/cases/${caseId}/trace`);
}

// ---- 判决书 API ----

/** GET /api/cases/{case_id}/report — 查询判决书 */
export async function getReport(caseId: string): Promise<DecisionReport | null> {
  if (USE_MOCK) return mockFetchReport(caseId);
  return request(`/cases/${caseId}/report`);
}

// ---- 历史记录 API ----

/** GET /api/history?user_id=... — 查询历史记录 */
export async function getHistory(): Promise<HistoryItem[]> {
  if (USE_MOCK) return (await mockFetchHistory()).items;
  return request(`/history?user_id=${USER_ID}`);
}

// ---- 观察清单 API ----

/** GET /api/watchlist?user_id=... — 查询观察清单 */
export async function getWatchlist(): Promise<WatchlistItem[]> {
  if (USE_MOCK) return (await mockFetchWatchlist()).items;
  return request(`/watchlist?user_id=${USER_ID}`);
}
