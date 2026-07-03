// ============================================================
// API 服务层
// 所有后端接口通过此模块统一导出。
// 当前使用 Mock 模式（USE_MOCK = true），切换后端时只需
// 注释 Mock 调用，取消注释 axios 调用即可。
// ============================================================

import {
  Case,
  CaseSummary,
  CreateCaseRequest,
  CreateCaseResponse,
  Message,
  PaginatedResponse,
  SessionState,
  SendMessageResponse,
  Verdict,
} from '../types';
import {
  fetchCaseList as mockFetchCaseList,
  fetchCaseDetail as mockFetchCaseDetail,
  createCase as mockCreateCase,
  fetchSessionMessages as mockFetchSessionMessages,
  fetchSessionState as mockFetchSessionState,
  sendMessage as mockSendMessage,
  fetchVerdict as mockFetchVerdict,
  fetchAllVerdicts as mockFetchAllVerdicts,
} from './mock';

// ---- 控制开关 ----
// 当后端 API 就绪时，将 USE_MOCK 设为 false 并配置 BASE_URL
const USE_MOCK = true;
const BASE_URL = '/api';

// ---- 工具 ----

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE_URL}${url}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) throw new Error(`API error: ${res.status} ${res.statusText}`);
  return res.json();
}

// ---- 案件 API ----

/** 获取案件列表（首页用） */
export async function getCaseList(
  page = 1,
  pageSize = 10,
): Promise<PaginatedResponse<CaseSummary>> {
  if (USE_MOCK) return mockFetchCaseList(page, pageSize);
  return request(`/cases?page=${page}&pageSize=${pageSize}`);
}

/** 获取单个案件详情 */
export async function getCaseDetail(caseId: string): Promise<Case | null> {
  if (USE_MOCK) return mockFetchCaseDetail(caseId);
  return request(`/cases/${caseId}`);
}

/** 创建新案件 */
export async function createCase(
  data: CreateCaseRequest,
): Promise<CreateCaseResponse> {
  if (USE_MOCK) return mockCreateCase(data);
  return request('/cases', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ---- 会话 API ----

/** 获取会话消息列表 */
export async function getSessionMessages(
  sessionId: string,
): Promise<Message[]> {
  if (USE_MOCK) return mockFetchSessionMessages(sessionId);
  return request(`/sessions/${sessionId}/messages`);
}

/** 获取会话状态 */
export async function getSessionState(
  sessionId: string,
): Promise<SessionState | null> {
  if (USE_MOCK) return mockFetchSessionState(sessionId);
  return request(`/sessions/${sessionId}/state`);
}

/** 发送消息 */
export async function sendMessage(
  sessionId: string,
  content: string,
): Promise<SendMessageResponse> {
  if (USE_MOCK) return mockSendMessage(sessionId, content);
  return request(`/sessions/${sessionId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ content }),
  });
}

// ---- 判决书 API ----

/** 获取判决书 */
export async function getVerdict(caseId: string): Promise<Verdict | null> {
  if (USE_MOCK) return mockFetchVerdict(caseId);
  return request(`/verdicts/${caseId}`);
}

/** 获取所有判决书（参考用） */
export async function getAllVerdicts(): Promise<Verdict[]> {
  if (USE_MOCK) return mockFetchAllVerdicts();
  return request('/verdicts');
}
