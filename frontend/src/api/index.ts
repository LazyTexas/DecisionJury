// ============================================================
// API 服务层
// 所有后端接口通过此模块统一导出。
// USE_MOCK = true 时使用 Mock 数据，false 时对接后端。
//
// 后端响应统一包裹在 { success, data, message } 中，
// request() 函数已自动提取 data 字段。
//
// 字段映射说明：
// - 后端 GET /cases/{id} 返回 case_status，前端 Case 用 status
//   getCaseDetail() 中做了映射
// - 后端 GET /cases/{id}/report 不返回 case_id，前端补充
//   getReport() 中做了补充
// ============================================================

import {
  Case,
  CaseSummary,
  CaseType,
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

/**
 * GET /api/cases/{case_id}
 *
 * 后端返回字段 case_status，前端 Case 接口用 status。
 * 这里做映射：case_status → status
 */
export async function getCaseDetail(caseId: string): Promise<Case | null> {
  if (USE_MOCK) return mockFetchCaseDetail(caseId);
  try {
    const raw = await request<Record<string, unknown>>(`/cases/${caseId}`);
    if (!raw) return null;
  // 映射后端 case_status → 前端 status
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

// ---- 消息 API ----

/** POST /api/chat — 发送消息 */
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
  return request('/chat', {
    method: 'POST',
    body: JSON.stringify({ user_id: USER_ID, case_id: caseId, message }),
  });
}

/** 获取消息列表（后端暂无此接口，仅 Mock 模式可用） */
export async function getCaseMessages(caseId: string): Promise<Message[]> {
  if (USE_MOCK) return mockFetchCaseMessages(caseId);
  return [];
}

// ---- Agent 分析 API ----

/** POST /api/cases/{case_id}/debate */
export async function startDebate(caseId: string): Promise<{
  case_id: string; case_status: string; steps: unknown[];
  rag_evidence: unknown[]; tool_results: unknown[]; report: DecisionReport;
}> {
  if (USE_MOCK) return mockStartDebate(caseId);
  return request(`/cases/${caseId}/debate`, {
    method: 'POST',
  });
}

/**
 * GET /api/cases/{case_id}/trace
 * 后端暂无此接口，Mock 模式可用
 */
export async function getTrace(caseId: string): Promise<{ case_id: string; trace: TraceItem[] }> {
  if (USE_MOCK) return mockFetchTrace(caseId);
  return { case_id: caseId, trace: [] };
}

// ---- 判决书 API ----

/**
 * GET /api/cases/{case_id}/report
 * 后端不返回 case_id，前端补充
 * 报告不存在时返回 null（不抛异常）
 */
export async function getReport(caseId: string): Promise<DecisionReport | null> {
  if (USE_MOCK) return mockFetchReport(caseId);
  try {
    const raw = await request<Record<string, unknown>>(`/cases/${caseId}/report`);
    if (!raw) return null;
    return {
      ...raw,
      case_id: (raw.case_id as string) ?? caseId,
    } as DecisionReport;
  } catch {
    return null;
  }
}
