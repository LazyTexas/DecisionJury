// ============================================================
// Mock 数据服务
// 在后端 API 就绪前，用本模块模拟全部接口响应。
// ============================================================

import {
  Case,
  CaseStatus,
  CaseType,
  Message,
  MessageRole,
  AgentStep,
  AgentName,
  RagEvidence,
  ToolResult,
  ToolName,
  RiskLevel,
  DecisionReport,
  TraceItem,
  CaseSummary,
  HistoryItem,
  HistoryResult,
  WatchlistItem,
  ShoppingDecision,
} from '../types';

// ---- 工具函数 ----

const generateId = (prefix: string): string =>
  `${prefix}_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;

const delay = (ms = 500): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

// ---- Mock 数据集 ----

const now = '2026-07-04T10:00:00+08:00';

const mockCases: Case[] = [
  {
    case_id: 'case_001',
    user_id: 'u001',
    case_type: CaseType.SHOPPING,
    title: '是否购买降噪耳机',
    description: '我想买一副 1299 元的降噪耳机，最近学习需要安静。',
    status: CaseStatus.COMPLETED,
    collected_fields: {
      price: 1299,
      monthly_budget_left: 2000,
      owned_alternatives: '普通耳机',
    },
    missing_fields: [],
    final_decision: ShoppingDecision.DELAY,
    report_id: 'report_001',
    created_at: '2026-07-01T10:00:00+08:00',
    updated_at: '2026-07-01T10:10:00+08:00',
  },
  {
    case_id: 'case_002',
    user_id: 'u001',
    case_type: CaseType.SHOPPING,
    title: '要不要买 MacBook Pro M4？',
    description: '现在用的 2019 Intel MacBook Pro 有点卡了，M4 性能提升很大但价格 2 万多。',
    status: CaseStatus.COLLECTING,
    collected_fields: {
      price: 21999,
    },
    missing_fields: ['monthly_budget_left', 'owned_alternatives'],
    final_decision: null,
    report_id: null,
    created_at: '2026-07-02T14:00:00+08:00',
    updated_at: '2026-07-02T14:00:00+08:00',
  },
  {
    case_id: 'case_003',
    user_id: 'u001',
    case_type: CaseType.TIME,
    title: '周末要不要去杭州旅游？',
    description: '朋友约我去杭州玩两天，但手头有工作下周截止，最近花销也大。',
    status: CaseStatus.READY_FOR_DEBATE,
    collected_fields: {
      hours_required: 16,
      free_hours_this_week: 20,
      urgent_tasks: 2,
    },
    missing_fields: [],
    final_decision: null,
    report_id: null,
    created_at: '2026-07-03T09:00:00+08:00',
    updated_at: '2026-07-03T09:30:00+08:00',
  },
];

const mockMessages: Record<string, Message[]> = {
  case_001: [
    { message_id: 'msg_001', case_id: 'case_001', role: MessageRole.USER, content: '我想买一副 1299 元的降噪耳机，最近学习需要安静。', created_at: '2026-07-01T10:00:00+08:00' },
    { message_id: 'msg_002', case_id: 'case_001', role: MessageRole.ASSISTANT, content: '明白。请问你本月预算还剩多少？是否已经有类似的耳机？', created_at: '2026-07-01T10:00:05+08:00' },
    { message_id: 'msg_003', case_id: 'case_001', role: MessageRole.USER, content: '我本月预算还剩 2000 元，已有一副普通耳机。', created_at: '2026-07-01T10:03:00+08:00' },
    { message_id: 'msg_004', case_id: 'case_001', role: MessageRole.ASSISTANT, content: '信息已补充。当前案件信息已经完整，可以进入正反方分析。', created_at: '2026-07-01T10:03:05+08:00' },
  ],
  case_002: [
    { message_id: 'msg_010', case_id: 'case_002', role: MessageRole.USER, content: '现在用的 2019 Intel MacBook Pro 有点卡了，M4 性能提升很大但价格 2 万多。', created_at: '2026-07-02T14:00:00+08:00' },
    { message_id: 'msg_011', case_id: 'case_002', role: MessageRole.ASSISTANT, content: '了解。请问你的预算大概是多少？旧电脑打算怎么处理？', created_at: '2026-07-02T14:00:05+08:00' },
  ],
  case_003: [
    { message_id: 'msg_020', case_id: 'case_003', role: MessageRole.USER, content: '朋友约我去杭州玩两天，但手头有工作下周截止，最近花销也大。', created_at: '2026-07-03T09:00:00+08:00' },
    { message_id: 'msg_021', case_id: 'case_003', role: MessageRole.ASSISTANT, content: '明白了。需要占用你多少小时？这周可支配时间有多少？紧急任务几个？', created_at: '2026-07-03T09:00:05+08:00' },
    { message_id: 'msg_022', case_id: 'case_003', role: MessageRole.USER, content: '大概需要 16 小时，这周空闲时间大约 20 小时，紧急任务有 2 个。', created_at: '2026-07-03T09:05:00+08:00' },
    { message_id: 'msg_023', case_id: 'case_003', role: MessageRole.ASSISTANT, content: '信息已收集完成，你现在可以启动辩论分析了。', created_at: '2026-07-03T09:30:00+08:00' },
  ],
};

const mockSteps: AgentStep[] = [
  {
    agent: AgentName.INPUT_PARSER,
    status: 'completed',
    summary: '识别为 shopping，信息完整。',
    confidence: 0.92,
    arguments: ['识别到商品价格、预算和替代品'],
    used_rag_ids: [],
    used_tool_names: [],
    error: null,
  },
  {
    agent: AgentName.PRO_AGENT,
    status: 'completed',
    summary: '该耳机能改善学习环境，存在明确使用场景。',
    confidence: 0.7,
    arguments: ['学习场景明确', '降噪功能与目标相关'],
    used_rag_ids: [],
    used_tool_names: [],
    error: null,
  },
  {
    agent: AgentName.CON_AGENT,
    status: 'completed',
    summary: '价格占剩余预算比例较高，且已有普通耳机。',
    confidence: 0.82,
    arguments: ['预算压力中等', '存在已有替代品'],
    used_rag_ids: ['history_001'],
    used_tool_names: [ToolName.COST_ANALYZER],
    error: null,
  },
  {
    agent: AgentName.JUDGE_AGENT,
    status: 'completed',
    summary: '建议暂缓 3 天后再决定。',
    confidence: 0.75,
    arguments: ['预算占比 65%', '历史存在电子产品闲置记录'],
    used_rag_ids: ['history_001'],
    used_tool_names: [ToolName.COST_ANALYZER, ToolName.COOLING_REMINDER],
    error: null,
  },
];

const mockRagEvidence: RagEvidence[] = [
  {
    id: 'history_001',
    title: '历史闲置记录',
    content: '用户曾购买蓝牙键盘后使用频率较低。',
    score: 0.82,
    source: 'decision_history',
    case_type: CaseType.SHOPPING,
    tags: ['electronics', 'idle'],
    created_at: '2026-06-20T12:00:00+08:00',
  },
];

const mockToolResults: ToolResult[] = [
  {
    tool_name: ToolName.COST_ANALYZER,
    status: 'success',
    summary: '该商品占剩余预算约 65%，预算压力中等。',
    risk_level: RiskLevel.MEDIUM,
    metrics: { budget_ratio: 0.65, budget_left_after_purchase: 701 },
    error: null,
  },
];

const mockReport: DecisionReport = {
  report_id: 'report_001',
  case_id: 'case_001',
  case_type: CaseType.SHOPPING,
  final_decision: ShoppingDecision.DELAY,
  confidence: 0.75,
  summary: '本案建议暂缓购买 3 天。',
  case_summary: '用户想购买 1299 元降噪耳机用于学习。',
  pro_points: ['存在学习降噪场景，可能提高专注度。'],
  con_points: ['价格占剩余预算较高，且已有普通耳机。'],
  rag_evidence: mockRagEvidence,
  tool_results: mockToolResults,
  next_actions: ['加入观察清单，3 天后复盘。'],
  created_at: now,
};

const mockTrace: TraceItem[] = [
  {
    trace_id: 'trace_001', step: 1, type: 'agent', name: AgentName.INPUT_PARSER,
    input_summary: '用户想购买降噪耳机', output_summary: '识别为 shopping，缺少预算和替代品信息',
    duration_ms: 900, status: 'completed', error: null,
  },
  {
    trace_id: 'trace_002', step: 2, type: 'rag_search', name: 'rag_search',
    input_summary: '降噪耳机 学习 电子产品', output_summary: '召回 1 条历史记录',
    duration_ms: 120, status: 'completed', error: null,
  },
];

const mockHistory: HistoryItem[] = [
  {
    history_id: 'history_001', user_id: 'u001', case_type: CaseType.SHOPPING,
    summary: '上个月购买蓝牙键盘后使用频率较低。', result: HistoryResult.REGRET,
    tags: ['electronics', 'idle'], created_at: '2026-06-20T12:00:00+08:00',
  },
];

const mockWatchlist: WatchlistItem[] = [
  {
    case_id: 'case_001', title: '降噪耳机', reason: '预算占比较高，建议冷静 3 天。',
    due_at: '2026-07-07T10:00:00+08:00', status: 'waiting',
  },
];

// ---- Mock API 函数 ----

/** 获取案件列表 */
export async function fetchCaseList(): Promise<CaseSummary[]> {
  await delay();
  return mockCases.map((c) => ({
    case_id: c.case_id,
    title: c.title,
    case_type: c.case_type,
    status: c.status,
    description: c.description,
    created_at: c.created_at,
    updated_at: c.updated_at,
    message_count: (mockMessages[c.case_id] ?? []).length,
    has_report: !!c.report_id,
  }));
}

/** 获取单个案件详情 */
export async function fetchCaseDetail(caseId: string): Promise<Case | null> {
  await delay();
  return mockCases.find((c) => c.case_id === caseId) ?? null;
}

/** 创建新案件 */
export async function createCase(data: {
  user_id: string; case_type: CaseType; title: string; description: string;
}): Promise<{ case: Case; next_question: string }> {
  await delay(800);
  const caseId = generateId('case');
  const newCase: Case = {
    case_id: caseId,
    user_id: data.user_id,
    case_type: data.case_type,
    title: data.title,
    description: data.description,
    status: CaseStatus.COLLECTING,
    collected_fields: {},
    missing_fields: [],
    final_decision: null,
    report_id: null,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  };
  mockCases.unshift(newCase);
  mockMessages[caseId] = [
    {
      message_id: generateId('msg'),
      case_id: caseId,
      role: MessageRole.ASSISTANT,
      content: '感谢你提交决策。为了帮你做出更好的决定，我需要先了解一些信息。请告诉我更多背景。',
      created_at: new Date().toISOString(),
    },
  ];
  return { case: newCase, next_question: '请描述你的预算和当前情况。' };
}

/** 获取会话消息列表 */
export async function fetchCaseMessages(caseId: string): Promise<Message[]> {
  await delay();
  return mockMessages[caseId] ?? [];
}

/** 发送消息（多轮补充信息） */
export async function sendMessage(
  caseId: string,
  _userId: string,
  content: string,
): Promise<{
  reply: string; case_status: CaseStatus; collected_fields: Record<string, unknown>; missing_fields: string[];
}> {
  await delay(800);
  const caseItem = mockCases.find((c) => c.case_id === caseId);
  const msgs = mockMessages[caseId] ?? [];
  const userMsgCount = msgs.filter((m) => m.role === MessageRole.USER).length;

  msgs.push({
    message_id: generateId('msg'), case_id: caseId, role: MessageRole.USER, content, created_at: new Date().toISOString(),
  });

  let reply: string;
  let collected: Record<string, unknown>;
  let missing: string[];
  let status: CaseStatus;

  if (userMsgCount < 1) {
    reply = '谢谢。请再告诉我：你有多着急做这个决定？有没有咨询过身边人的意见？';
    collected = { ...caseItem?.collected_fields, last_answer: content };
    missing = ['urgency', 'peer_opinion'];
    status = CaseStatus.COLLECTING;
  } else {
    reply = '信息已补充。当前案件信息已经完整，可以进入正反方分析。';
    collected = { price: 1299, monthly_budget_left: 2000, owned_alternatives: '普通耳机' };
    missing = [];
    status = CaseStatus.READY_FOR_DEBATE;
  }

  if (caseItem) {
    caseItem.status = status;
    caseItem.collected_fields = collected;
    caseItem.missing_fields = missing;
    caseItem.updated_at = new Date().toISOString();
  }
  mockMessages[caseId] = msgs;

  return { reply, case_status: status, collected_fields: collected, missing_fields: missing };
}

/** 启动多 Agent 辩论 */
export async function startDebate(
  caseId: string,
): Promise<{
  case_id: string; case_status: CaseStatus; steps: AgentStep[];
  rag_evidence: RagEvidence[]; tool_results: ToolResult[]; report: DecisionReport;
}> {
  await delay(2000);
  const caseItem = mockCases.find((c) => c.case_id === caseId);
  if (caseItem) {
    caseItem.status = CaseStatus.COMPLETED;
    caseItem.final_decision = mockReport.final_decision;
    caseItem.report_id = mockReport.report_id;
    caseItem.updated_at = new Date().toISOString();
  }
  return {
    case_id: caseId,
    case_status: CaseStatus.COMPLETED,
    steps: mockSteps,
    rag_evidence: mockRagEvidence,
    tool_results: mockToolResults,
    report: mockReport,
  };
}

/** 获取判决书 */
export async function fetchReport(caseId: string): Promise<DecisionReport | null> {
  await delay();
  const c = mockCases.find((x) => x.case_id === caseId);
  if (!c?.report_id) return null;
  return { ...mockReport, report_id: c.report_id };
}

/** 获取 Agent 执行轨迹 */
export async function fetchTrace(caseId: string): Promise<{ case_id: string; trace: TraceItem[] }> {
  await delay();
  return { case_id: caseId, trace: mockTrace };
}

/** 获取历史记录 */
export async function fetchHistory(): Promise<{ items: HistoryItem[] }> {
  await delay();
  return { items: mockHistory };
}

/** 获取观察清单 */
export async function fetchWatchlist(): Promise<{ items: WatchlistItem[] }> {
  await delay();
  return { items: mockWatchlist };
}
