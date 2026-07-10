// ============================================================
// DecisionJury 前端类型定义（接口契约）
// 本文件定义了前后端通信的全部数据结构。
// 后端（成员 B）应按此契约实现 API。
// 字段名统一使用 snake_case，与后端 API 文档对齐。
// ============================================================

// ---- 枚举 ----

/** 案件状态 */
export enum CaseStatus {
  COLLECTING = 'collecting',
  READY_FOR_DEBATE = 'ready_for_debate',
  DEBATING = 'debating',
  COMPLETED = 'completed',
  REJECTED = 'rejected',
  ARCHIVED = 'archived',
}

/** 消息角色 */
export enum MessageRole {
  USER = 'user',
  ASSISTANT = 'assistant',
  AGENT = 'agent',
}

/** 决策类别 */
export enum CaseType {
  SHOPPING = 'shopping',
  TIME = 'time',
}

/** 购物决策最终裁决 */
export enum ShoppingDecision {
  BUY = 'buy',
  DELAY = 'delay',
  REJECT = 'reject',
  ALTERNATIVE = 'alternative',
}

/** 时间决策最终裁决 */
export enum TimeDecision {
  ACCEPT = 'accept',
  PARTIAL_ACCEPT = 'partial_accept',
  DELAY = 'delay',
  REJECT = 'reject',
}

/** Agent 名称 */
export enum AgentName {
  INPUT_PARSER = 'input_parser',
  PRO_AGENT = 'pro_agent',
  CON_AGENT = 'con_agent',
  JUDGE_AGENT = 'judge_agent',
}

/** 工具名称 */
export enum ToolName {
  COST_ANALYZER = 'cost_analyzer',
  COOLING_REMINDER = 'cooling_reminder',
  DECISION_SCORE = 'decision_score',
}

/** 风险等级 */
export enum RiskLevel {
  LOW = 'low',
  MEDIUM = 'medium',
  HIGH = 'high',
}

/** 历史记录结果 */
export enum HistoryResult {
  WORTH = 'worth',
  REGRET = 'regret',
  NEUTRAL = 'neutral',
}

// ---- 公共数据结构 ----

/** 案件 */
export interface Case {
  case_id: string;
  user_id: string;
  case_type: CaseType;
  title: string;
  description: string;
  status: CaseStatus;
  collected_fields: Record<string, unknown>;
  missing_fields: string[];
  final_decision: string | null;
  report_id: string | null;
  created_at: string | null;
  updated_at: string | null;
}

/** 消息 */
export interface Message {
  message_id: string;
  case_id: string;
  role: MessageRole;
  content: string;
  created_at: string;
}

/** Agent 执行步骤 */
export interface AgentStep {
  agent: AgentName;
  status: 'completed' | 'failed';
  summary: string;
  confidence: number;
  arguments: string[];
  used_rag_ids: string[];
  used_tool_names: string[];
  error: string | null;
}

/** RAG 证据 */
export interface RagEvidence {
  id: string;
  title: string;
  content: string;
  score: number;
  source: string;
  case_type: CaseType;
  tags: string[];
  created_at: string | null;
}

/** 工具调用结果 */
export interface ToolResult {
  tool_name: ToolName | string;
  status: 'success' | 'failed';
  summary: string;
  risk_level: RiskLevel | null;
  metrics: Record<string, unknown>;
  error: string | null;
}

/** 判决书 */
export interface DecisionReport {
  report_id: string;
  case_id: string;
  case_type: CaseType;
  final_decision: string;
  confidence: number;
  summary: string;
  case_summary: string;
  pro_points: string[];
  con_points: string[];
  rag_evidence: RagEvidence[];
  tool_results: ToolResult[];
  next_actions: string[];
  created_at: string;
}

/** Agent 执行轨迹项 */
export interface TraceItem {
  trace_id: string;
  step: number;
  type: 'agent' | 'rag_search' | 'tool_call';
  name: string;
  input_summary: string;
  output_summary: string;
  duration_ms: number;
  status: 'completed' | 'failed';
  error: string | null;
}

/** 案件摘要（列表页用） */
export interface CaseSummary {
  case_id: string;
  title: string;
  case_type: CaseType;
  status: CaseStatus;
  description: string;
  created_at: string | null;
  updated_at: string | null;
  message_count: number;
  has_report: boolean;
}

/** 历史记录 */
export interface HistoryItem {
  history_id: string;
  user_id: string;
  case_type: CaseType;
  title: string;
  summary: string;
  result: HistoryResult;
  tags: string[];
  case_id: string;
  report_id: string | null;
  created_at: string;
}

/** 观察清单项 */
export interface WatchlistItem {
  case_id: string;
  title: string;
  reason: string;
  due_at: string;
  status: 'waiting' | 'completed' | 'expired';
}

// ---- 请求 / 响应 DTO ----

/** 创建案件请求 */
export interface CreateCaseRequest {
  user_id: string;
  case_type: CaseType;
  title: string;
  description: string;
}

/** 创建案件响应（匹配后端 CreateCaseResponse） */
export interface CreateCaseResponse {
  case_id: string;
  case_status: string;
  collected_fields: Record<string, unknown>;
  missing_fields: string[];
  next_question: string | null;
}

/** 发送消息请求（匹配后端 POST /api/cases/{case_id}/messages） */
export interface SendMessageRequest {
  user_id: string;
  message: string;
}

/** 发送消息响应 */
export interface SendMessageResponse {
  reply: string;
  case_status: string;
  collected_fields: Record<string, unknown>;
  missing_fields: string[];
}

/** 启动辩论请求 */
export interface DebateRequest {
  user_id: string;
}

/** 启动辩论响应 */
export interface DebateResponse {
  case_id: string;
  case_status: string;
  steps: AgentStep[];
  rag_evidence: RagEvidence[];
  tool_results: ToolResult[];
  report: DecisionReport;
}

/** 查询案件详情响应（后端返回扁平对象） */
export interface CaseDetailResponse {
  case_id: string;
  user_id: string;
  case_type: string;
  title: string;
  description: string;
  case_status: string;
  collected_fields: Record<string, unknown>;
  missing_fields: string[];
  final_decision: string | null;
  report_id: string | null;
  created_at: string;
  updated_at: string;
}

/** 查询判决书响应 */
export interface ReportResponse {
  report: DecisionReport;
}

/** 查询轨迹响应 */
export interface TraceResponse {
  case_id: string;
  trace: TraceItem[];
}

/** 查询历史记录响应 */
export interface HistoryResponse {
  items: HistoryItem[];
}

/** 添加历史记录请求 */
export interface CreateHistoryRequest {
  user_id: string;
  case_type: CaseType;
  summary: string;
  result: HistoryResult;
  tags: string[];
}

/** 提交决策复盘请求 */
export interface FeedbackRequest {
  user_id: string;
  actual_action: string;
  satisfaction: number;
  review: string;
}

/** 查询观察清单响应 */
export interface WatchlistResponse {
  items: WatchlistItem[];
}

/** RAG 检索请求 */
export interface RAGSearchRequest {
  user_id: string;
  case_id: string;
  case_type: CaseType;
  query: string;
  top_k: number;
}

/** RAG 检索响应 */
export interface RAGSearchResponse {
  results: RagEvidence[];
}

/** 成本计算请求（购物场景） */
export interface CostAnalyzerShoppingRequest {
  case_id: string;
  case_type: CaseType.SHOPPING;
  price: number;
  monthly_budget_left: number;
}

/** 成本计算请求（时间场景） */
export interface CostAnalyzerTimeRequest {
  case_id: string;
  case_type: CaseType.TIME;
  hours_required: number;
  free_hours_this_week: number;
  urgent_tasks: number;
}

/** 冷静期提醒请求 */
export interface CoolingReminderRequest {
  user_id: string;
  case_id: string;
  title: string;
  cooling_days: number;
  reason: string;
  watch_items: string[];
}

// ---- 工具类型 ----

/** 通用成功响应 */
export interface ApiSuccessResponse<T> {
  success: true;
  data: T;
  message: string;
}

/** 通用错误响应 */
export interface ApiErrorResponse {
  success: false;
  data: null;
  message: string;
}

export type ApiResponse<T> = ApiSuccessResponse<T> | ApiErrorResponse;

/** 分页响应（匹配后端 page_size / total 命名） */
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  page_size: number;
}
