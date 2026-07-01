// ============================================================
// DecisionJury 前端类型定义（接口契约）
// 本文件定义了前后端通信的全部数据结构。
// 后端（成员 B）应按此契约实现 API。
// ============================================================

// ---- 枚举 ----

/** 案件状态 */
export enum CaseStatus {
  /** 进行中（信息收集中） */
  IN_PROGRESS = 'in_progress',
  /** 等待辩论 */
  PENDING_DEBATE = 'pending_debate',
  /** 辩论中 */
  DEBATING = 'debating',
  /** 已判决 */
  VERDICTED = 'verdict',
  /** 已关闭 */
  CLOSED = 'closed',
}

/** 消息角色 */
export enum MessageRole {
  /** 用户 */
  USER = 'user',
  /** 系统/助手 */
  ASSISTANT = 'assistant',
  /** 正方 Agent */
  PRO_AGENT = 'pro_agent',
  /** 反方 Agent */
  CON_AGENT = 'con_agent',
  /** 法官 Agent */
  JUDGE = 'judge',
}

/** 消息类型 */
export enum MessageType {
  /** 普通文本 */
  TEXT = 'text',
  /** 追问（系统需要用户补充信息） */
  QUESTION = 'question',
  /** 辩论陈述 */
  ARGUMENT = 'argument',
  /** 判决 */
  VERDICT = 'verdict',
  /** 系统提示 */
  SYSTEM = 'system',
}

/** 决策类别 */
export enum DecisionCategory {
  /** 购物决策 */
  SHOPPING = 'shopping',
  /** 时间/日程决策 */
  TIME = 'time',
  /** 职业决策 */
  CAREER = 'career',
  /** 关系决策 */
  RELATIONSHIP = 'relationship',
  /** 财务决策 */
  FINANCE = 'finance',
  /** 其他 */
  OTHER = 'other',
}

/** 对话阶段 */
export enum SessionStage {
  /** 信息收集 */
  INFO_COLLECTION = 'info_collection',
  /** 正方辩论 */
  PRO_DEBATE = 'pro_debate',
  /** 反方辩论 */
  CON_DEBATE = 'con_debate',
  /** 法官裁决 */
  JUDGE_RULING = 'judge_ruling',
  /** 已完成 */
  COMPLETED = 'completed',
}

/** 判决倾向 */
export enum VerdictTendency {
  /** 支持 */
  SUPPORT = 'support',
  /** 反对 */
  OPPOSE = 'oppose',
  /** 中立/需更多信息 */
  NEUTRAL = 'neutral',
}

// ---- 核心实体 ----

/** 案件 */
export interface Case {
  /** 案件唯一 ID */
  id: string;
  /** 案件标题（用户输入的决策问题） */
  title: string;
  /** 决策类别 */
  category: DecisionCategory;
  /** 案件状态 */
  status: CaseStatus;
  /** 用户初始描述 */
  description: string;
  /** 当前对话阶段 */
  currentStage: SessionStage;
  /** 关联会话 ID */
  sessionId: string;
  /** 创建时间（ISO 8601） */
  createdAt: string;
  /** 更新时间（ISO 8601） */
  updatedAt: string;
  /** 关联判决书 ID（判决后才有） */
  verdictId?: string;
}

/** 创建案件请求 */
export interface CreateCaseRequest {
  /** 决策问题标题 */
  title: string;
  /** 决策类别 */
  category: DecisionCategory;
  /** 初始描述 */
  description: string;
}

/** 创建案件响应 */
export interface CreateCaseResponse {
  /** 创建的案件 */
  case: Case;
  /** 初始会话 ID */
  sessionId: string;
  /** 系统的首条回复消息 */
  firstMessage: Message;
}

/** 会话 */
export interface Session {
  /** 会话唯一 ID */
  id: string;
  /** 所属案件 ID */
  caseId: string;
  /** 当前对话阶段 */
  stage: SessionStage;
  /** 会话状态快照 */
  state: SessionState;
  /** 消息列表 */
  messages: Message[];
  /** 创建时间 */
  createdAt: string;
  /** 更新时间 */
  updatedAt: string;
}

/** 会话状态（记录收集到的决策信息） */
export interface SessionState {
  /** 用户目标 / 决策目标 */
  goal?: string;
  /** 预算范围（如适用） */
  budget?: string;
  /** 时间压力（紧迫程度 1-10） */
  timePressure?: number;
  /** 用户偏好 */
  preferences?: string[];
  /** 已收集的补充信息键值对 */
  extraInfo: Record<string, string>;
  /** 当前正在被追问的字段名 */
  pendingQuestion?: string;
  /** 正方法庭陈述 */
  proArgument?: string;
  /** 反方法庭陈述 */
  conArgument?: string;
}

/** 消息 */
export interface Message {
  /** 消息唯一 ID */
  id: string;
  /** 所属会话 ID */
  sessionId: string;
  /** 发送角色 */
  role: MessageRole;
  /** 消息类型 */
  type: MessageType;
  /** 消息内容 */
  content: string;
  /** 发送时间 */
  createdAt: string;
  /** 元数据（Agent 调用链路、工具调用等） */
  metadata?: MessageMetadata;
}

/** 消息元数据 */
export interface MessageMetadata {
  /** Agent 名称（Agent 消息时） */
  agentName?: string;
  /** 调用的工具列表 */
  toolCalls?: ToolCall[];
  /** 推理过程（对 Agent 可见） */
  reasoning?: string;
  /** 置信度 0-1 */
  confidence?: number;
}

/** 工具调用记录 */
export interface ToolCall {
  /** 工具名称 */
  toolName: string;
  /** 输入参数 */
  input: Record<string, unknown>;
  /** 输出结果 */
  output: string;
  /** 调用状态 */
  status: 'success' | 'error';
  /** 耗时（ms） */
  durationMs: number;
}

/** 发送消息请求 */
export interface SendMessageRequest {
  /** 消息内容 */
  content: string;
  /** 会话 ID */
  sessionId: string;
}

/** 发送消息响应 */
export interface SendMessageResponse {
  /** 用户消息 */
  userMessage: Message;
  /** 助手回复消息列表（可能多条，如多个 Agent 轮流发言） */
  assistantMessages: Message[];
  /** 更新后的会话状态 */
  sessionState: SessionState;
  /** 当前阶段 */
  currentStage: SessionStage;
  /** 是否已完成所有阶段 */
  isCompleted: boolean;
}

/** 判决书 */
export interface Verdict {
  /** 判决书唯一 ID */
  id: string;
  /** 所属案件 ID */
  caseId: string;
  /** 判决标题 */
  title: string;
  /** 最终倾向 */
  tendency: VerdictTendency;
  /** 判决结论摘要 */
  conclusion: string;
  /** 详细分析 */
  analysis: string;
  /** 正反双方论点总结 */
  arguments: VerdictArguments;
  /** 判决理由 */
  reasons: string[];
  /** 给用户的建议 */
  suggestion: string;
  /** 置信度评分 0-100 */
  confidenceScore: number;
  /** 相关历史案例参考 */
  relatedCases?: string[];
  /** 生成时间 */
  createdAt: string;
}

/** 判决书中的论点总结 */
export interface VerdictArguments {
  /** 正方论点 */
  pro: string[];
  /** 反方论点 */
  con: string[];
}

/** 案件摘要（列表页用） */
export interface CaseSummary {
  id: string;
  title: string;
  category: DecisionCategory;
  status: CaseStatus;
  stage: SessionStage;
  createdAt: string;
  updatedAt: string;
  /** 消息总数 */
  messageCount: number;
  /** 是否有判决书 */
  hasVerdict: boolean;
}

/** 分页请求 */
export interface PaginationRequest {
  page: number;
  pageSize: number;
}

/** 分页响应 */
export interface PaginatedResponse<T> {
  data: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

/** API 通用响应包装 */
export interface ApiResponse<T> {
  code: number;
  message: string;
  data: T;
}