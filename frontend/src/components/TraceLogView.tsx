// ============================================================
// TraceLogView：完整 Agent 执行轨迹视图（全屏模态，庭审笔录式时间线）
// 纯前端组件。数据来源为 report 里已由后端返回的 debate_events / tool_results。
// 展示顺序：书记员 → 正方 → 反方 → 法官；工具调用以等宽小块嵌入。
// ============================================================

import { useMemo } from 'react';
import type { DecisionReport, ToolResult } from '../types';
import { TRACE_NAME_LABEL } from '../constants';

interface TraceLogViewProps {
  open: boolean;
  caseId: string;
  report: DecisionReport | null;
  onClose: () => void;
}

/** 角色徽章信息（speaker → 标签/颜色类名） */
const SPEAKER_META: Record<string, { label: string; className: string }> = {
  clerk: { label: '书记员', className: 's-clerk' },
  pro_agent: { label: '正方', className: 's-pro' },
  con_agent: { label: '反方', className: 's-con' },
  judge_agent: { label: '法官', className: 's-judge' },
};

const PHASE_LABEL: Record<string, string> = {
  case_summary: '庭审开场 · 案情概述',
  opening_statement: '正方结案陈词',
  closing_argument: '反方结案陈词',
  verdict: '法官裁决',
};

/** 工具名 → 中文（复用 TRACE_NAME_LABEL 语义，缺失时原样返回） */
function toolLabel(name: string): string {
  return TRACE_NAME_LABEL[name] ?? name;
}

export default function TraceLogView({ open, caseId, report, onClose }: TraceLogViewProps) {
  const events = useMemo(() => (report?.debate_events ?? []).slice().sort((a, b) => a.order - b.order), [report]);

  if (!open) return null;
  if (!report) return null;

  // 关联工具结果（供工具调用块展示 metrics）
  const toolMap = new Map<string, ToolResult>();
  (report.tool_results || []).forEach((tr) => {
    if (!toolMap.has(tr.tool_name)) toolMap.set(tr.tool_name, tr);
  });

  const title = report.case_summary || `${report.case_id} 决策分析`;
  const speakerCount = events.length > 0 ? events.length : 0;

  return (
    <div className="overlay" onClick={onClose}>
      <div className="tracelog" role="dialog" aria-label="Agent 执行轨迹" onClick={(e) => e.stopPropagation()}>
        <div className="tl-head">
          <div>
            <div className="tl-kicker">DecisionJury · 冷静裁判庭</div>
            <h3>完整 Agent 执行轨迹</h3>
            <p className="tl-sub">{title}</p>
          </div>
          <button className="modal-x" aria-label="关闭" onClick={onClose}>×</button>
        </div>

        <div className="tl-toolbar">
          <span className="tl-tag">案号 {caseId}</span>
          <span className="tl-tag">{speakerCount} 条发言</span>
          <span className="tl-tag tl-tag-ok">多 Agent 协作完成</span>
        </div>

        <div className="tl-body">
          {/* 角色说明图例 */}
          <div className="tl-legend">
            {(Object.keys(SPEAKER_META)).map((k) => (
              <span key={k} className={`tl-legend-item ${SPEAKER_META[k].className}`}>{SPEAKER_META[k].label}</span>
            ))}
          </div>

          {/* 发言时间线 */}
          {events.length === 0 ? (
            <p className="muted" style={{ textAlign: 'center', padding: '40px 0' }}>暂无庭审发言记录。</p>
          ) : (
            <div className="tl-timeline">
              {events.map((ev) => {
                const meta = SPEAKER_META[ev.speaker] ?? { label: ev.speaker, className: 's-default' };
                const phaseText = PHASE_LABEL[ev.phase] ?? ev.phase;
                // 该发言引用到的工具，从 evidence 里挑工具名
                const toolRefs = (ev.evidence || [])
                  .map((id) => toolMap.get(id))
                  .filter((t): t is ToolResult => Boolean(t));
                return (
                  <div key={ev.event_id} className="tl-event">
                    <div className={`tl-dot ${meta.className}`} />
                    <div className="tl-card">
                      <div className="tl-row">
                        <span className={`tl-speaker ${meta.className}`}>{meta.label}</span>
                        <span className="tl-phase">{phaseText}</span>
                      </div>
                      <p className="tl-content">{ev.content}</p>
                      {toolRefs.length > 0 && (
                        <div className="tl-tools">
                          {toolRefs.map((t) => (
                            <div key={t.tool_name + t.summary} className="tl-tool">
                              <b>{toolLabel(t.tool_name)}</b>
                              <span>{t.summary}</span>
                              {t.metrics && Object.keys(t.metrics).length > 0 && (
                                <div className="tl-metrics">
                                  {Object.entries(t.metrics).map(([k, v]) => (
                                    <span key={k} className="tl-metric">{k}: {String(v)}</span>
                                  ))}
                                </div>
                              )}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
