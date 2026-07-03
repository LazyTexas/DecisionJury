// ============================================================
// Mock 数据服务
// 在后端 API 就绪前，用本模块模拟全部接口响应。
// 切换方式：在 src/api/index.ts 中将 API 调用指向本模块。
// ============================================================

import {
  Case,
  CaseStatus,
  CaseSummary,
  DecisionCategory,
  Message,
  MessageRole,
  MessageType,
  PaginatedResponse,
  SessionStage,
  SessionState,
  Verdict,
  VerdictTendency,
} from '../types';

// ---- 工具函数 ----

const generateId = (): string => {
  return Math.random().toString(36).substring(2, 15);
};

const delay = (ms = 500): Promise<void> =>
  new Promise((resolve) => setTimeout(resolve, ms));

// ---- Mock 数据集 ----

const mockCases: Case[] = [
  {
    id: 'case-001',
    title: '要不要买这台 MacBook Pro M4？',
    category: DecisionCategory.SHOPPING,
    status: CaseStatus.VERDICTED,
    currentStage: SessionStage.COMPLETED,
    sessionId: 'session-001',
    description: '我现在用的是 2019 年的 Intel MacBook Pro，最近感觉有点卡了。看到新出的 M4 性能提升很大，但价格要 2 万多，有点犹豫。',
    createdAt: '2026-06-20T10:00:00Z',
    updatedAt: '2026-06-22T15:30:00Z',
    verdictId: 'verdict-001',
  },
  {
    id: 'case-002',
    title: '要不要接这个 Freelance 项目？',
    category: DecisionCategory.CAREER,
    status: CaseStatus.IN_PROGRESS,
    currentStage: SessionStage.INFO_COLLECTION,
    sessionId: 'session-002',
    description: '有个 Freelance 项目找我，做三个月的前端开发，报酬不错但是时间很紧。我现在本身工作也忙，担心忙不过来。',
    createdAt: '2026-06-28T09:00:00Z',
    updatedAt: '2026-06-28T09:00:00Z',
  },
  {
    id: 'case-003',
    title: '周末要不要去杭州旅游？',
    category: DecisionCategory.TIME,
    status: CaseStatus.PENDING_DEBATE,
    currentStage: SessionStage.INFO_COLLECTION,
    sessionId: 'session-003',
    description: '这周末朋友约我去杭州玩两天，但我手头有个工作下周截止，而且最近花销有点大。',
    createdAt: '2026-06-29T14:00:00Z',
    updatedAt: '2026-06-29T14:00:00Z',
  },
  {
    id: 'case-004',
    title: 'AirPods Pro 2 现在值得入手吗？',
    category: DecisionCategory.SHOPPING,
    status: CaseStatus.DEBATING,
    currentStage: SessionStage.PRO_DEBATE,
    sessionId: 'session-004',
    description: '我的旧耳机坏了一个月了，一直忍着没买。看到 AirPods Pro 2 最近降价了，但听说第三代快出了。',
    createdAt: '2026-06-25T11:00:00Z',
    updatedAt: '2026-06-29T16:00:00Z',
  },
  {
    id: 'case-005',
    title: '要不要报那个三万块的训练营？',
    category: DecisionCategory.FINANCE,
    status: CaseStatus.CLOSED,
    currentStage: SessionStage.COMPLETED,
    sessionId: 'session-005',
    description: '一个 AI 训练营，三个月，承诺就业推荐。学费三万，可以分期。我现在工作两年了，想转 AI 方向。',
    createdAt: '2026-06-15T08:00:00Z',
    updatedAt: '2026-06-18T12:00:00Z',
    verdictId: 'verdict-005',
  },
];

// Mock 消息（按会话分组）
const mockMessages: Record<string, Message[]> = {
  'session-001': [
    {
      id: 'msg-001-1',
      sessionId: 'session-001',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '我现在用的是 2019 年的 Intel MacBook Pro，最近感觉有点卡了。看到新出的 M4 性能提升很大，但价格要 2 万多，有点犹豫。',
      createdAt: '2026-06-20T10:00:00Z',
    },
    {
      id: 'msg-001-2',
      sessionId: 'session-001',
      role: MessageRole.ASSISTANT,
      type: MessageType.QUESTION,
      content: '感谢你提交这个决策！我来帮你理清思路。\n\n首先请问：**你的预算是多少？** 是打算全额支付还是有分期计划？另外，新电脑的主要使用场景是什么？日常办公、编程开发、还是视频剪辑等重度工作？',
      createdAt: '2026-06-20T10:00:05Z',
      metadata: {
        agentName: '信息收集 Agent',
        reasoning: '用户提到价格敏感，需要先明确预算和使用场景',
      },
    },
    {
      id: 'msg-001-3',
      sessionId: 'session-001',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '预算大概 2-2.5 万吧，分期也行。主要用来写代码（前端开发），偶尔剪点视频。',
      createdAt: '2026-06-20T10:05:00Z',
    },
    {
      id: 'msg-001-4',
      sessionId: 'session-001',
      role: MessageRole.ASSISTANT,
      type: MessageType.QUESTION,
      content: '明白了！再问你几个问题：\n\n1. **时间压力**：你有多着急换电脑？是还能忍几个月，还是已经影响工作了？\n2. **旧电脑处理**：旧的那台 2019 款，你打算怎么处理？卖掉抵一部分费用吗？\n3. **有没有看过竞品**：Windows 笔记本是否在考虑范围内？',
      createdAt: '2026-06-20T10:05:10Z',
    },
    {
      id: 'msg-001-5',
      sessionId: 'session-001',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '还能忍一两个月吧，但确实影响了开发效率。旧电脑打算留着当备用机。Windows 不考虑，习惯了 macOS 生态。',
      createdAt: '2026-06-20T10:10:00Z',
    },
    {
      id: 'msg-001-6',
      sessionId: 'session-001',
      role: MessageRole.ASSISTANT,
      type: MessageType.SYSTEM,
      content: '信息收集完成，准备进入辩论阶段。正在检索相关历史案例……',
      createdAt: '2026-06-20T10:10:05Z',
    },
    {
      id: 'msg-001-7',
      sessionId: 'session-001',
      role: MessageRole.PRO_AGENT,
      type: MessageType.ARGUMENT,
      content: '**正方观点：应该买 ✅**\n\n1. **生产力提升**：M4 相比 Intel 在编译速度上提升 3-4 倍，每天节省的时间累积起来非常可观。\n2. **长期价值**：一台 MacBook 正常用 4-5 年，分摊到每天成本不到 15 元。\n3. **时机成熟**：M4 已经发布一段时间，生态完善，没有早期适配问题。\n4. **使用场景匹配**：前端开发和视频剪辑正是 M4 的优势领域。',
      createdAt: '2026-06-20T11:00:00Z',
      metadata: {
        agentName: '正方 Agent',
        reasoning: '用户预算充足、使用场景匹配、旧电脑已影响效率，建议购买',
        confidence: 0.85,
      },
    },
    {
      id: 'msg-001-8',
      sessionId: 'session-001',
      role: MessageRole.CON_AGENT,
      type: MessageType.ARGUMENT,
      content: '**反方观点：建议等待 ❌**\n\n1. **财务考虑**：2 万多元是一笔不小的开支，且旧电脑并非完全不能用。\n2. **迭代周期**：M4 是初代，根据苹果惯例，M5 可能在明年有更大提升。\n3. **替代方案**：是否可以先用公司电脑或升级内存来延长旧电脑寿命？\n4. **非刚性需求**：既然还能忍一两个月，说明需求并不紧急。',
      createdAt: '2026-06-20T11:05:00Z',
      metadata: {
        agentName: '反方 Agent',
        reasoning: '用户并非无电脑可用，财务上也不够紧迫，建议观察等待',
        confidence: 0.7,
      },
    },
    {
      id: 'msg-001-9',
      sessionId: 'session-001',
      role: MessageRole.JUDGE,
      type: MessageType.VERDICT,
      content: '**⚖️ 最终判决：建议购买 MacBook Pro M4**\n\n经过正反双方的辩论，考虑到你的具体情况，我的最终建议是购买。\n\n关键理由：\n1. 旧电脑已明显影响工作效率，属于生产力投资而非消费\n2. 预算在可接受范围内\n3. 使用场景（前端开发 + 视频剪辑）与 M4 的优势高度匹配\n4. M5 即使明年发布，现有 M4 也完全够用 3-4 年\n\n**建议**：可以等到 618 或教育优惠期间入手，可能省下 1000-2000 元。',
      createdAt: '2026-06-20T12:00:00Z',
      metadata: {
        agentName: '法官 Agent',
        confidence: 0.9,
      },
    },
  ],
  'session-002': [
    {
      id: 'msg-002-1',
      sessionId: 'session-002',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '有个 Freelance 项目找我，做三个月的前端开发，报酬不错但是时间很紧。我现在本身工作也忙，担心忙不过来。',
      createdAt: '2026-06-28T09:00:00Z',
    },
    {
      id: 'msg-002-2',
      sessionId: 'session-002',
      role: MessageRole.ASSISTANT,
      type: MessageType.QUESTION,
      content: '感谢提交决策！先了解几个关键信息：\n\n1. **报酬具体是多少？** 跟你的时薪比如何？\n2. **你目前的工作强度**：平均每天加班吗？周末是否经常需要工作？\n3. **这个项目对你的职业发展有帮助吗？** 比如新技术栈、新行业经验？',
      createdAt: '2026-06-28T09:00:05Z',
    },
  ],
  'session-003': [
    {
      id: 'msg-003-1',
      sessionId: 'session-003',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '这周末朋友约我去杭州玩两天，但我手头有个工作下周截止，而且最近花销有点大。',
      createdAt: '2026-06-29T14:00:00Z',
    },
  ],
  'session-004': [
    {
      id: 'msg-004-1',
      sessionId: 'session-004',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '我的旧耳机坏了一个月了，一直忍着没买。看到 AirPods Pro 2 最近降价了，但听说第三代快出了。',
      createdAt: '2026-06-25T11:00:00Z',
    },
    {
      id: 'msg-004-2',
      sessionId: 'session-004',
      role: MessageRole.ASSISTANT,
      type: MessageType.QUESTION,
      content: '了解！先问你几个问题：\n\n1. **你每天使用耳机的场景是什么？** 通勤、办公、还是运动？\n2. **没有耳机的这一个月**，对你的生活有多大影响？\n3. **你的预算上限**是多少？',
      createdAt: '2026-06-25T11:00:05Z',
    },
    {
      id: 'msg-004-3',
      sessionId: 'session-004',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '主要是通勤和办公时用。这一个月确实不方便。预算 2000 以内吧。',
      createdAt: '2026-06-25T11:05:00Z',
    },
    {
      id: 'msg-004-4',
      sessionId: 'session-004',
      role: MessageRole.ASSISTANT,
      type: MessageType.SYSTEM,
      content: '信息收集完成，准备进入辩论阶段。正在准备正反方论点……',
      createdAt: '2026-06-29T16:00:00Z',
    },
  ],
  'session-005': [
    {
      id: 'msg-005-1',
      sessionId: 'session-005',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '一个 AI 训练营，三个月，承诺就业推荐。学费三万，可以分期。我现在工作两年了，想转 AI 方向。',
      createdAt: '2026-06-15T08:00:00Z',
    },
    {
      id: 'msg-005-2',
      sessionId: 'session-005',
      role: MessageRole.ASSISTANT,
      type: MessageType.QUESTION,
      content: '好问题！先了解几个情况：\n\n1. **你现在的工作是什么？** 跟 AI 相关吗？\n2. **为什么想转 AI？** 是兴趣驱动还是看到行业趋势？\n3. **三万块对你来说**，是多大比例的收入？\n4. **了解过这个训练营的口碑吗？** 有没有往期学员的反馈？',
      createdAt: '2026-06-15T08:00:05Z',
    },
    {
      id: 'msg-005-3',
      sessionId: 'session-005',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '现在做后端开发，跟 AI 不太相关。主要是觉得 AI 是未来的方向，不想被淘汰。三万块差不多是一个月的工资。口碑看了下，评价两极分化，有的说好有的说坑。',
      createdAt: '2026-06-15T08:05:00Z',
    },
    {
      id: 'msg-005-4',
      sessionId: 'session-005',
      role: MessageRole.ASSISTANT,
      type: MessageType.QUESTION,
      content: '了解了。再问问：\n\n1. **你自学的动力和能力如何？** AI 方向很多免费/低成本资源，你有没有尝试过自学？\n2. **训练营的课程大纲**方便分享吗？具体教什么技术栈？\n3. **就业推荐的承诺**有合同保障吗？还是口头承诺？',
      createdAt: '2026-06-15T08:05:10Z',
    },
    {
      id: 'msg-005-5',
      sessionId: 'session-005',
      role: MessageRole.USER,
      type: MessageType.TEXT,
      content: '自学过一段时间，但坚持不下来，缺少氛围和方向。课程内容主要是 NLP 和 LLM 应用开发。就业推荐是写在合同里的。',
      createdAt: '2026-06-15T08:10:00Z',
    },
    {
      id: 'msg-005-6',
      sessionId: 'session-005',
      role: MessageRole.ASSISTANT,
      type: MessageType.SYSTEM,
      content: '信息收集完成，准备辩论阶段。',
      createdAt: '2026-06-15T08:10:05Z',
    },
    {
      id: 'msg-005-7',
      sessionId: 'session-005',
      role: MessageRole.PRO_AGENT,
      type: MessageType.ARGUMENT,
      content: '**正方观点：应该报名 ✅**\n\n1. **方向正确**：AI 是明确的行业趋势，早转型早受益。\n2. **解决痛点**：用户自学的最大障碍是缺乏方向和氛围，结构化课程正好解决这个问题。\n3. **合同保障**：有就业推荐条款，降低风险。\n4. **分期减轻压力**：三万分期后每月压力可控。',
      createdAt: '2026-06-15T09:00:00Z',
    },
    {
      id: 'msg-005-8',
      sessionId: 'session-005',
      role: MessageRole.CON_AGENT,
      type: MessageType.ARGUMENT,
      content: '**反方观点：建议不报名 ❌**\n\n1. **性价比存疑**：三万块等于一个月工资，成本很高。\n2. **口碑两极**：评价分化说明质量不稳定，有踩坑风险。\n3. **自学能力更重要**：AI 领域变化快，训练营出来后还是要持续自学。不如先用这个钱报一些便宜的系统课程，培养自学能力。\n4. **就业推荐 ≠ 保就业**：推荐面试不等于保证录取。',
      createdAt: '2026-06-15T09:05:00Z',
    },
    {
      id: 'msg-005-9',
      sessionId: 'session-005',
      role: MessageRole.JUDGE,
      type: MessageType.VERDICT,
      content: '**⚖️ 最终判决：暂不建议报名**\n\n正反双方辩论后，综合考虑，建议现阶段暂不报名这个训练营。\n\n关键理由：\n1. 训练营口碑两极，风险较高\n2. 三万块的沉没成本压力大\n3. 可以先从低成本方式试水，确定真正兴趣再做重投入\n\n**替代建议**：\n- 先花 500-1000 元报个入门网课（如 Coursera 的 Andrew Ng AI 课程）\n- 加入 AI 相关的开发者社区/线下 Meetup\n- 在自己工作中尝试引入 AI 工具，积累实操经验\n- 如果三个月后仍确定想转，再考虑训练营也不迟',
      createdAt: '2026-06-15T10:00:00Z',
    },
  ],
};

// Mock 判决书
const mockVerdicts: Record<string, Verdict> = {
  'verdict-001': {
    id: 'verdict-001',
    caseId: 'case-001',
    title: '关于是否购买 MacBook Pro M4 的判决书',
    tendency: VerdictTendency.SUPPORT,
    conclusion: '建议购买 MacBook Pro M4。旧电脑已明显影响工作效率，预算和使用场景与产品匹配度高，属于生产力投资而非消费性支出。',
    analysis: '用户目前使用 2019 款 Intel MacBook Pro，已出现性能瓶颈影响开发效率。预算 2-2.5 万在合理范围内，使用场景涵盖前端开发和视频剪辑，是 M4 芯片的优势领域。虽然 M5 可能在明年发布，但 M4 的性能完全满足未来 3-4 年需求。建议观望到促销节点入手以节省开支。',
    arguments: {
      pro: [
        'M4 比 Intel 编译速度提升 3-4 倍，显著提升生产力',
        '分摊到每天成本不到 15 元，长期价值可观',
        'M4 生态已完善，无早期适配问题',
        '前端开发和视频剪辑正是 M4 优势领域',
      ],
      con: [
        '2 万多元是一笔较大开支',
        'M5 可能在明年有更大提升',
        '可以考虑先用公司电脑过渡',
        '还能再忍说明并非极端紧急',
      ],
    },
    reasons: [
      '旧电脑已显著影响开发效率，属于生产力瓶颈',
      '用户预算充足且使用场景高度匹配',
      'M4 产品周期成熟，不存在"买就亏"的问题',
      '相比等待，尽早提升生产力带来的收益更大',
    ],
    suggestion: '建议在 618 或教育优惠期间入手，可能节省 1000-2000 元。型号建议 14 寸 MacBook Pro M4 Pro 芯片 + 24GB 内存的配置，平衡性能与价格。旧的 Intel MacBook 可以挂二手平台出售，回血约 3000-5000 元。',
    confidenceScore: 85,
    relatedCases: ['case-004'],
    createdAt: '2026-06-22T15:30:00Z',
  },
  'verdict-005': {
    id: 'verdict-005',
    caseId: 'case-005',
    title: '关于是否报名 AI 训练营的判决书',
    tendency: VerdictTendency.OPPOSE,
    conclusion: '暂不建议报名三万块的 AI 训练营。风险较高、性价比不明确。建议先通过低成本方式试水 AI 方向，确认兴趣后再做重投入。',
    analysis: '用户有转 AI 的想法，但训练营口碑两极分化，且三万块为一个月的工资，沉没成本较高。用户的痛点在于缺乏自学方向和氛围，结构化课程确实能解决这个问题，但可以先通过更便宜的方式（线上课程、社区、实践项目）验证自己的兴趣和毅力。',
    arguments: {
      pro: [
        'AI 是明确的行业趋势，早转型早受益',
        '结构化课程解决自学缺乏方向的问题',
        '合同中有就业推荐条款',
        '分期后每月压力可控',
      ],
      con: [
        '三万块等一个月工资，成本较高',
        '口碑两极，质量不稳定',
        'AI 领域变化快，最终还是要靠自学能力',
        '就业推荐 ≠ 保就业',
      ],
    },
    reasons: [
      '训练营口碑两极分化，存在踩坑风险',
      '三万块的沉没成本压力较大',
      '存在低成本的替代试水方案',
      '用户的转行动机较泛，需先确认具体方向',
    ],
    suggestion: '建议先花 500-1000 元报入门网课（如 Andrew Ng 的 AI 课程），同时在工作中尝试引入 AI 工具积累实操经验。三个月后如果仍然坚定想转 AI，再评估是否值得投入训练营。另外可以关注一些有退款保障或分期更灵活的训练营项目。',
    confidenceScore: 78,
    relatedCases: [],
    createdAt: '2026-06-18T12:00:00Z',
  },
};

// Mock 会话状态
const mockSessionStates: Record<string, SessionState> = {
  'session-001': {
    goal: '购买 MacBook Pro M4',
    budget: '20000-25000',
    timePressure: 6,
    preferences: ['macOS 生态', '前端开发', '视频剪辑'],
    extraInfo: {
      旧电脑处理方式: '留作备用机',
      是否考虑Windows: '不考虑',
    },
    proArgument: 'M4 性能提升显著，使用场景匹配，长期价值高',
    conArgument: '价格高，M5 即将发布，非刚性需求',
  },
  'session-002': {
    goal: '决定是否接 Freelance 项目',
    extraInfo: {},
    pendingQuestion: '报酬和时薪比',
  },
  'session-003': {
    goal: '决定周末是否去杭州旅游',
    extraInfo: {},
    pendingQuestion: undefined,
  },
  'session-004': {
    goal: '决定是否购买 AirPods Pro 2',
    budget: '2000',
    timePressure: 8,
    preferences: ['通勤使用', '办公使用'],
    extraInfo: {
      旧耳机状态: '坏了已一个月',
    },
    proArgument: '已准备好正方案例',
  },
  'session-005': {
    goal: '决定是否报名 AI 训练营',
    budget: '30000（分期）',
    timePressure: 5,
    preferences: ['AI行业', 'NLP', 'LLM应用开发'],
    extraInfo: {
      当前工作: '后端开发',
      口碑: '评价两极分化',
      就业推荐: '合同保障',
    },
    proArgument: '方向正确，解决自学痛点',
    conArgument: '性价比存疑，口碑两极',
  },
};

// ---- Mock API 函数 ----

/** 获取案件列表 */
export async function fetchCaseList(
  page = 1,
  pageSize = 10,
): Promise<PaginatedResponse<CaseSummary>> {
  await delay();
  const summaries: CaseSummary[] = mockCases.map((c) => ({
    id: c.id,
    title: c.title,
    category: c.category,
    status: c.status,
    stage: c.currentStage,
    createdAt: c.createdAt,
    updatedAt: c.updatedAt,
    messageCount: (mockMessages[c.sessionId] ?? []).length,
    hasVerdict: !!c.verdictId,
  }));

  const total = summaries.length;
  const totalPages = Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize;
  const end = start + pageSize;

  return {
    data: summaries.slice(start, end),
    total,
    page,
    pageSize,
    totalPages,
  };
}

/** 获取单个案件详情 */
export async function fetchCaseDetail(caseId: string): Promise<Case | null> {
  await delay();
  return mockCases.find((c) => c.id === caseId) ?? null;
}

/** 创建新案件 */
export async function createCase(data: {
 title: string; category: DecisionCategory; description: string
}): Promise<{
  case: Case; sessionId: string; firstMessage: Message
}> {
  await delay(800);
  const sessionId = `session-${generateId()}`;
  const caseId = `case-${generateId()}`;
  const now = new Date().toISOString();

  const newCase: Case = {
    id: caseId,
    title: data.title,
    category: data.category,
    status: CaseStatus.IN_PROGRESS,
    currentStage: SessionStage.INFO_COLLECTION,
    sessionId,
    description: data.description,
    createdAt: now,
    updatedAt: now,
  };

  const firstMessage: Message = {
    id: `msg-${generateId()}`,
    sessionId,
    role: MessageRole.ASSISTANT,
    type: MessageType.QUESTION,
    content: `感谢你提交决策：「${data.title}」\n\n为了帮你做出更好的决定，我需要先了解一些信息。请告诉我更多关于这个决定的背景，比如：\n\n1. **你为什么在纠结这个决定？**\n2. **对你来说最重要的考量因素是什么？**（价格、时间、效果、他人意见？）\n3. **有没有一个截止时间？**`,
    createdAt: now,
    metadata: {
      agentName: '信息收集 Agent',
    },
  };

  // 写入 mock 数据
  mockCases.unshift(newCase);
  mockMessages[sessionId] = [firstMessage];
  mockSessionStates[sessionId] = {
    goal: data.title,
    extraInfo: {},
  };

  return {
    case: newCase,
    sessionId,
    firstMessage,
  };
}

/** 获取会话消息列表 */
export async function fetchSessionMessages(
  sessionId: string,
): Promise<Message[]> {
  await delay();
  return mockMessages[sessionId] ?? [];
}

/** 获取会话状态 */
export async function fetchSessionState(
  sessionId: string,
): Promise<SessionState | null> {
  await delay();
  return mockSessionStates[sessionId] ?? null;
}

/** 发送消息（模拟多轮对话） */
export async function sendMessage(
  sessionId: string,
  content: string,
): Promise<{
  userMessage: Message;
  assistantMessages: Message[];
  sessionState: SessionState;
  currentStage: SessionStage;
  isCompleted: boolean;
}> {
  await delay(1200);

  const now = new Date().toISOString();
  const state = mockSessionStates[sessionId] ?? {
    goal: '',
    extraInfo: {},
  };
  const messages = mockMessages[sessionId] ?? [];
  const currentMsgCount = messages.length;

  // 用户消息
  const userMsg: Message = {
    id: `msg-${generateId()}`,
    sessionId,
    role: MessageRole.USER,
    type: MessageType.TEXT,
    content,
    createdAt: now,
  };

  // 根据当前消息数量模拟不同阶段的响应
  const assistantMessages: Message[] = [];

  if (currentMsgCount < 3) {
    // 信息收集阶段：继续追问
    const questions = [
      {
        content: '谢谢你的回答！再问一下：\n\n1. **这个决定有没有截止日期？** 你需要在什么时间之前做出决定？\n2. **如果选择不做/不买**，会有什么后果吗？\n3. **有没有咨询过身边人的意见？** 他们怎么说？',
        field: '截止日期',
      },
      {
        content: '好的，越来越清晰了！还有几个问题：\n\n1. **过去的类似决策中**，你通常是后悔做了还是后悔没做？\n2. **如果忽略价格因素**，你内心的第一选择是什么？\n3. **你希望这个决定能带来什么改变？**',
        field: '历史决策模式',
      },
    ];

    const qi = Math.min(Math.floor(currentMsgCount / 2), questions.length - 1);
    const q = questions[qi];

    assistantMessages.push({
      id: `msg-${generateId()}`,
      sessionId,
      role: MessageRole.ASSISTANT,
      type: MessageType.QUESTION,
      content: q.content,
      createdAt: now,
      metadata: {
        agentName: '信息收集 Agent',
      },
    });

    state.pendingQuestion = q.field;
  } else if (currentMsgCount < 6) {
    // 进入辩论阶段
    assistantMessages.push(
      {
        id: `msg-${generateId()}`,
        sessionId,
        role: MessageRole.ASSISTANT,
        type: MessageType.SYSTEM,
        content: '信息已收集完毕！现在进入**正反方辩论阶段**。\n\n正方 Agent 正在准备论点……',
        createdAt: now,
      },
      {
        id: `msg-${generateId()}`,
        sessionId,
        role: MessageRole.PRO_AGENT,
        type: MessageType.ARGUMENT,
        content: '**正方观点：支持 ✅**\n\n经过分析，我认为这个决定值得积极推进。理由如下：\n\n1. **用户已有明确的需求和动机**，不是一时冲动\n2. **经过信息收集**，用户的基本条件（预算/时间/偏好）都满足要求\n3. **决策的收益大于风险**，值得尝试\n\n当然，最终还需要综合反方的意见来看。',
        createdAt: now,
        metadata: {
          agentName: '正方 Agent',
          confidence: 0.8,
        },
      },
      {
        id: `msg-${generateId()}`,
        sessionId,
        role: MessageRole.CON_AGENT,
        type: MessageType.ARGUMENT,
        content: '**反方观点：建议谨慎 ❌**\n\n从审慎角度出发，我有不同看法：\n\n1. **"想要"和"需要"有区别**，用户需要区分这是真需求还是消费冲动\n2. **机会成本**：这笔资源（时间/金钱）是否有更好的用途？\n3. **建议设置冷静期**：等 48 小时后再做最终决定\n\n建议用户认真考虑这些风险因素。',
        createdAt: now,
        metadata: {
          agentName: '反方 Agent',
          confidence: 0.7,
        },
      },
    );
  } else {
    // 最终判决阶段
    assistantMessages.push({
      id: `msg-${generateId()}`,
      sessionId,
      role: MessageRole.JUDGE,
      type: MessageType.VERDICT,
      content: '**⚖️ 最终判决**\n\n感谢你的耐心等待！经过正反双方的充分辩论，综合考虑你的个人情况，我的最终判决如下：\n\n**建议：可以做，但有前提条件。**\n\n关键考量：\n1. 你的需求和条件都匹配，这是理性决定而非冲动消费\n2. 正反双方都有合理论点，但正方的论据更贴合你的实际状况\n3. 建议采取"冷静期法则"——如果 48 小时后你仍然想做，那就去做\n\n**具体建议**：\n- 如果决定做，建议先设定清晰的目标和预算上限\n- 执行前再做一次成本收益的书面分析\n- 完成后回来复盘，帮助未来的决策\n\n希望这份判决对你有帮助！',
      createdAt: now,
      metadata: {
        agentName: '法官 Agent',
        confidence: 0.85,
      },
    });
  }

  // 更新会话状态
  const stage: SessionStage =
    currentMsgCount < 3
      ? SessionStage.INFO_COLLECTION
      : currentMsgCount < 6
        ? SessionStage.PRO_DEBATE
        : SessionStage.COMPLETED;

  state.extraInfo = {
    ...state.extraInfo,
    最近一次回答: content.substring(0, 50) + (content.length > 50 ? '...' : ''),
  };

  // 保存消息
  messages.push(userMsg, ...assistantMessages);
  mockMessages[sessionId] = messages;
  mockSessionStates[sessionId] = state;

  return {
    userMessage: userMsg,
    assistantMessages,
    sessionState: state,
    currentStage: stage,
    isCompleted: stage === SessionStage.COMPLETED,
  };
}

/** 获取判决书 */
export async function fetchVerdict(
  caseId: string,
): Promise<Verdict | null> {
  await delay();
  const c = mockCases.find((c) => c.id === caseId);
  if (!c?.verdictId) return null;
  return mockVerdicts[c.verdictId] ?? null;
}

/** 获取所有判决书（供案例参考） */
export async function fetchAllVerdicts(): Promise<Verdict[]> {
  await delay();
  return Object.values(mockVerdicts);
}