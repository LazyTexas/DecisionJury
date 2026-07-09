// ============================================================
// API 服务层
// 所有后端接口通过此模块统一导出。
// USE_MOCK = true 时使用 Mock 数据，false 时对接后端。
// ============================================================

import {
  Case,
  CaseSummary,
  CaseType,
  HistoryItem,
  Message,
  SendMessageResponse,
  DecisionReport,
  TraceItem,
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
} from './mock';

const USE_MOCK = false;
const BASE_URL = '/api';
const USER_ID = 'local_user';

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
  return request(`/cases?user_id=${USER_ID}&page=${page}&page_size=${pageSize}`);
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

export async function createCase(req: {
  case_type: CaseType; title: string; description: string;
}): Promise<{
  case_id: string; case_status: string;
  collected_fields: Record<string, unknown>; missing_fields: string[];
  next_question: string | null;
}> {
  if (USE_MOCK) {
    const res = await mockCreateCase({ user_id: USER_ID, ...req });
    return {
      case_id: res.case.case_id,
      case_status: res.case.status,
      collected_fields: {},
      missing_fields: [],
      next_question: null,
    };
  }
  return request('/cases', {
    method: 'POST',
    body: JSON.stringify({ user_id: USER_ID, ...req }),
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
      body: JSON.stringify({ user_id: USER_ID, ...data }),
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

export async function getCaseMessages(caseId: string): Promise<Message[]> {
  if (USE_MOCK) return mockFetchCaseMessages(caseId);
  return [];
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
    const mock = (await import('./mock')).fetchHistory;
    return (await mock()) as any;
  }
  const query = new URLSearchParams({ user_id: USER_ID });
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
    body: JSON.stringify({ user_id: USER_ID, ...data }),
  });
}
