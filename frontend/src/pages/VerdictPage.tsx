import { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getReport, getTrace } from '../api';
import { DECISION_META, CASE_TYPE_META, TRACE_NAME_LABEL, TRACE_TYPE_LABEL } from '../constants';
import { formatDateTime } from '../utils/format';
import type { DecisionReport, RagEvidence, ToolResult, TraceItem } from '../types';
import FeedbackModal from '../components/FeedbackModal';

const nodeColor: Record<string, [string, string]> = {
  input_parser: ['#3B5BDB', '解'], rag_search: ['#7C5CBF', '检'], cost_analyzer: ['#0E9AA7', '算'],
  pro_agent: ['#2F9E5B', '正'], con_agent: ['#E5484D', '反'], cooling_reminder: ['#D4A017', '醒'], judge_agent: ['#3B5BDB', '判'],
};

const C = 2 * Math.PI * 66;

export default function VerdictPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [report, setReport] = useState<DecisionReport | null>(null);
  const [trace, setTrace] = useState<TraceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    Promise.all([getReport(caseId), getTrace(caseId).catch(() => ({ case_id: caseId, trace: [] }))])
      .then(([r, t]) => { setReport(r); setTrace(t.trace); })
      .catch(() => setReport(null))
      .finally(() => setLoading(false));
  }, [caseId]);

  const meta = useMemo(() => (report ? DECISION_META[report.final_decision] : undefined), [report]);
  const gaugeOffset = useMemo(() => (report ? C * (1 - Math.min(1, Math.max(0, report.confidence))) : C), [report]);

  return (
    <div>
      {loading ? (<div className="card"><p className="muted">加载判决书中…</p></div>) : !report ? (<div className="card"><p className="muted">尚未生成判决书，请先完成辩论分析。</p><button className="btn ghost" style={{ marginTop: 16 }} onClick={() => navigate('/chat/' + caseId)}>回到对话</button></div>) : (
        <>
          <div className="verdict-head"><div className="kicker">DecisionJury · 冷静裁判庭</div><h1>判决书</h1><div className="muted">案号：{report.case_id} · {CASE_TYPE_META[report.case_type]?.label ?? report.case_type} · {report.case_summary}</div></div>
          <div className="flowzone"><div className="label"><span style={{ width: 8, height: 8, borderRadius: '50%', background: 'var(--pro)', display: 'inline-block' }}></span>分析执行过程 · {trace.length} 步 · 全部完成</div><div className="flow">
            {trace.map((t) => { const [color, glyph] = nodeColor[t.name] ?? ['#3B5BDB', '·']; return (
              <div key={t.trace_id} className="node"><div className="n-ico" style={{ background: color }}>{glyph}</div><div className="n-name">{TRACE_NAME_LABEL[t.name] ?? t.name}</div><div className="n-meta">{TRACE_TYPE_LABEL[t.type] ?? t.type} · {t.duration_ms}ms</div><div className="n-ok">✓</div><div className="conn"></div></div>
            ); })}
          </div></div>
          <div className="letter">
            <p className="lead">你正在犹豫：{report.case_summary}。我们检索了你过去的决策记录，并核算了成本。以下是完整的分析过程与最终建议——结论供你参考，最终仍由你决定。</p>
            <div className="arg"><div className="col"><h2 className="arg-title">正方观点</h2><h4><span className="dot" style={{ background: 'var(--pro)' }}></span>收益</h4><ul>{(report.pro_points || []).map((p, i) => <li key={i}>{p}</li>)}</ul></div><div className="col con"><h2 className="arg-title">反方观点</h2><h4><span className="dot" style={{ background: 'var(--con)' }}></span>风险</h4><ul>{(report.con_points || []).map((p, i) => <li key={i}>{p}</li>)}</ul></div></div>
            <h2>历史证据（RAG）</h2>
            {(report.rag_evidence || []).length === 0 ? <p className="muted">无引用证据。</p> : (report.rag_evidence || []).map((ev: RagEvidence, i) => (<div key={ev.id} className="cite"><div className="no">{i + 1}</div><div className="ct"><b>{ev.title}</b><span className="score">相关性 {ev.score}</span><p>{ev.content}</p></div></div>))}
            <h2>工具计算结果</h2>
            <div className="toolrow">{(report.tool_results || []).map((tr: ToolResult, i) => (<div key={i} className="toolbox"><div className="t-name"><span className="tag tool" style={{ background: 'var(--brand-soft)', color: 'var(--tool)' }}>工具</span>{tr.tool_name}</div><p className="tiny" style={{ marginTop: 8 }}>{tr.summary}</p>{tr.risk_level && <p className="tiny">风险：{tr.risk_level}</p>}</div>))}</div>
            <h2>最终裁决</h2>
            <div className="verdict-badge"><div className="vlabel">{meta?.label ?? report.final_decision}</div><div className="gauge"><svg viewBox="0 0 160 160"><circle className="track" cx="80" cy="80" r="66" /><circle className="p" cx="80" cy="80" r="66" transform="rotate(-90 80 80)" style={{ strokeDasharray: C, strokeDashoffset: gaugeOffset }} /></svg><div className="val"><b>{report.confidence}</b><span>法官置信度</span></div></div><p className="muted" style={{ maxWidth: 520 }}>{report.summary}</p></div>
            <h2>后续动作</h2><ul className="actions">{(report.next_actions || []).map((a, i) => <li key={i}><span className="i">{i + 1}</span>{a}</li>)}</ul>
            <div className="sig"><p>DecisionJury · 冷静裁判庭</p><p className="tiny">生成于 {formatDateTime(report.created_at)} · 报告 {report.report_id}</p><div className="stamp"><b>冷静裁判庭</b><span>判决专用章</span></div></div>
            <div style={{ textAlign: 'center', marginTop: 20 }}><button className="btn ghost" onClick={() => setFeedbackOpen(true)}>提交决策复盘</button></div>
          </div>
          <FeedbackModal caseId={caseId!} open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
        </>
      )}
    </div>
  );
}