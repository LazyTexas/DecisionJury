// ============================================================
// 展示层共享常量
// 枚举 → 中文标签 / 颜色。图标等 JSX 内容保留在各页面内部。
// ============================================================

import { CaseStatus, CaseType, HistoryResult } from './types';

/** 案件状态 → 文案/颜色 */
export const CASE_STATUS_META: Record<CaseStatus, { label: string; color: string }> = {
  [CaseStatus.COLLECTING]: { label: '信息收集中', color: 'processing' },
  [CaseStatus.READY_FOR_DEBATE]: { label: '待辩论', color: 'warning' },
  [CaseStatus.DEBATING]: { label: '辩论中', color: 'processing' },
  [CaseStatus.COMPLETED]: { label: '已判决', color: 'success' },
  [CaseStatus.REJECTED]: { label: '已拒绝', color: 'error' },
  [CaseStatus.ARCHIVED]: { label: '已归档', color: 'default' },
};

/** 案件类别 → 文案/颜色 */
export const CASE_TYPE_META: Record<CaseType, { label: string; color: string }> = {
  [CaseType.SHOPPING]: { label: '购物', color: 'blue' },
  [CaseType.TIME]: { label: '时间决策', color: 'orange' },
};

/** 历史结果 → 文案/颜色/表情 */
export const HISTORY_RESULT_META: Record<HistoryResult, { label: string; color: string; icon: string }> = {
  [HistoryResult.WORTH]: { label: '满意', color: 'green', icon: '👍' },
  [HistoryResult.REGRET]: { label: '后悔', color: 'red', icon: '👎' },
  [HistoryResult.NEUTRAL]: { label: '中立', color: 'default', icon: '🤔' },
};

/** 最终裁决 → 文案/颜色（与后端 final_decision 对齐） */
export const DECISION_META: Record<string, { label: string; color: string }> = {
  buy: { label: '建议购买', color: 'success' },
  accept: { label: '建议接受', color: 'success' },
  partial_accept: { label: '建议部分接受', color: 'processing' },
  delay: { label: '建议暂缓', color: 'warning' },
  reject: { label: '建议不购买 / 拒绝', color: 'error' },
  alternative: { label: '建议寻找替代方案', color: 'default' },
};

/** trace.name → 中文（执行轨迹展示用） */
export const TRACE_NAME_LABEL: Record<string, string> = {
  input_parser: '信息解析',
  rag_search: '历史证据检索',
  cost_analyzer: '成本分析工具',
  pro_agent: '正方论证',
  con_agent: '反方论证',
  cooling_reminder: '冷静期提醒工具',
  judge_agent: '法官裁决',
};

/** trace.type → 中文 */
export const TRACE_TYPE_LABEL: Record<string, string> = {
  agent: 'Agent 步骤',
  rag_search: 'RAG 检索',
  tool_call: '工具调用',
};

/** 后端必填字段英文 key → 中文（信息收集进度提示用） */
export const FIELD_LABELS: Record<string, Record<string, string>> = {
  shopping: {
    product_name: '商品名称',
    price: '价格',
    purpose: '使用目的',
    monthly_budget_left: '本月剩余预算',
    owned_alternatives: '已有替代品',
    expected_usage_frequency: '预期使用频率',
    trigger_reason: '触发原因',
  },
  time: {
    hours_required: '所需小时数',
    free_hours_this_week: '本周可支配时间',
    urgent_tasks: '紧急任务数',
  },
};

/** 取字段中文名，未知 key 原样返回 */
export function fieldLabel(caseType: string, key: string): string {
  const table = FIELD_LABELS[caseType];
  if (table && table[key]) return table[key];
  return key;
}
