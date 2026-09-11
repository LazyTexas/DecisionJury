import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { getCaseDetail, getCaseMessages, sendMessage, startDebateStream, saveLocalMessages } from '../api';
import { CASE_STATUS_META, fieldLabel } from '../constants';
import { MessageRole, CaseStatus, CaseType } from '../types';
import type { Case, Message, ReplyPlan } from '../types';

const roleName: Record<MessageRole, string> = { user: '你', assistant: '决策助手', agent: 'Agent' };
const roleColor: Record<MessageRole, string> = { user: 'var(--brand)', assistant: 'var(--pro)', agent: 'var(--gold)' };
// 辩论阶段的展示名：进度条上按这个顺序亮起
const STAGE_LABELS: Record<string, string> = {
  parse: '确认材料',
  rag: '检索历史复盘',
  tools: '成本与评分',
  pro_agent: '正方发言',
  con_agent: '反方发言',
  judge_agent: '法官评议',
};

export default function ChatPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [sending, setSending] = useState(false);
  const [debating, setDebating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // 最近一轮的回复计划：快捷选项与“可以结束了”的提示由它驱动
  const [plan, setPlan] = useState<ReplyPlan | null>(null);
  // 辩论阶段的实时进度：正方/反方一完成就把论点显示出来，不再白等 30 秒
  const [stages, setStages] = useState<{ stage: string; status: string; summary?: string; arguments?: string[] }[]>([]);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!caseId) return;
    Promise.all([getCaseDetail(caseId), getCaseMessages(caseId)])
      .then(([c, msgs]) => { setCaseData(c); setMessages(msgs); })
      .catch((e) => setError((e as Error).message || '加载失败'))
      .finally(() => setLoading(false));
  }, [caseId]);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages, sending, debating, plan]);

  const isTime = caseData?.case_type === CaseType.TIME;
  const canDebate = caseData?.status === CaseStatus.READY_FOR_DEBATE && !isTime && !debating;
  const isCompleted = caseData?.status === CaseStatus.COMPLETED;
  const isRejected = caseData?.status === CaseStatus.REJECTED;
  // 只有七项全齐才锁输入框：核心信息齐了仍允许继续补充（否则用户没法纠正/回答可选问题）
  const isFullyReady = caseData?.status === CaseStatus.READY_FOR_DEBATE && (caseData?.missing_fields ?? []).length === 0;
  const inputLocked = isCompleted || isRejected || debating || isFullyReady;

  const commit = (updater: (prev: Message[]) => Message[]) => setMessages((prev) => { const next = updater(prev); if (caseId) saveLocalMessages(caseId, next); return next; });

  const send = async (textOverride?: string) => {
    const text = (textOverride ?? input).trim();
    if (!text || sending || debating || !caseId || !caseData) return;
    const userMsg: Message = { message_id: 'u' + Date.now(), case_id: caseId, role: MessageRole.USER, content: text, created_at: new Date().toISOString() };
    commit((prev) => [...prev, userMsg]);
    setInput(''); setPlan(null); setSending(true); setError(null);
    try {
      const res = await sendMessage(caseId, text);
      commit((prev) => [...prev, { message_id: 'a' + Date.now(), case_id: caseId, role: MessageRole.ASSISTANT, content: res.reply, created_at: new Date().toISOString() }]);
      setPlan(res.reply_plan ?? null);
      setCaseData((prev) => (prev ? { ...prev, status: res.case_status as CaseStatus, collected_fields: res.collected_fields, missing_fields: res.missing_fields } : prev));
      // 用户明确说“直接分析”时自动进入辩论，不再让人多点一次按钮
      if (res.reply_plan?.stop_requested && res.case_status === CaseStatus.READY_FOR_DEBATE) {
        setTimeout(() => { void debate(); }, 400);
      }
    } catch (e) { setError((e as Error).message || '发送失败'); } finally { setSending(false); }
  };

  const debate = async () => {
    if (!caseId || debating) return;
    setDebating(true); setError(null); setStages([]);
    try {
      const result = await startDebateStream(caseId, (event) => {
        setStages((prev) => {
          const next = prev.filter((s) => s.stage !== event.stage);
          next.push({ stage: event.stage, status: event.status ?? 'running', summary: event.summary, arguments: event.arguments });
          return next;
        });
      });
      if (result?.report) { navigate('/verdict/' + caseId); return; }
      setError('辩论未生成判决书');
    } catch (e) {
      setError((e as Error).message || '启动辩论失败');
    } finally {
      setDebating(false);
    }
    // 兜底：无论流式解析成功与否，都回查一次案件状态。
    // 服务端可能已经生成了判决书（真实事故：前端没解包 SSE 信封 → 报告已落库但页面不跳转，
    // 用户反复点击又只会拿到 MISSING_FIELDS）。这里以服务端状态为准，能跳就直接跳。
    try {
      const fresh = await getCaseDetail(caseId);
      setCaseData(fresh);
      if (fresh?.status === CaseStatus.COMPLETED) navigate('/verdict/' + caseId);
    } catch { /* 回查失败不影响主流程，保留上面的错误提示 */ }
  };

  const missing = (caseData?.missing_fields ?? []).filter((f) => !isTime);

  return (
    <div>
      <div className="hero" style={{ paddingTop: 26, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between' }}>
        <div><h1 className="serif">{caseData?.title ?? '信息收集'}</h1><p>逐步补全决策所需的信息，系统会针对关键字段追问。</p></div>
        <span className="tag gold">{caseData ? CASE_STATUS_META[caseData.status]?.label ?? caseData.status : ''}</span>
      </div>
      {isTime && (<div className="card" style={{ marginBottom: 16, borderColor: 'var(--gold)', background: 'color-mix(in srgb,var(--gold) 8%,var(--panel))' }}><p className="muted">时间决策分析即将上线，当前可查看已有记录。</p></div>)}
      {isRejected && (<div className="card" style={{ marginBottom: 16, borderColor: 'var(--con)', background: 'color-mix(in srgb,var(--con) 8%,var(--panel))' }}><p className="muted">该决策超出系统支持范围（如医疗、投资、法律等），已停止分析。</p></div>)}
      {error && (<div className="card" style={{ marginBottom: 16, borderColor: 'var(--con)' }}><p style={{ color: 'var(--con)' }}>{error}</p></div>)}

      <div className="grid2">
        <div className="card">
          <div id="chatMsgs">
            {messages.length === 0 ? <p className="muted">暂无消息，先说第一句吧。</p> : messages.map((m) => (<div key={m.message_id} className={"bubble " + (m.role === MessageRole.USER ? 'user' : 'asst')}><b style={{ fontSize: 12, color: 'var(--ink3)' }}>{roleName[m.role]}</b><p style={{ marginTop: 4 }}>{m.content}</p></div>))}
            <div ref={endRef} />
          </div>
          {(plan?.chips?.length ?? 0) > 0 && (
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14 }}>
              {(plan?.chips ?? []).map((chip) => (
                <button key={chip} className="btn ghost" style={{ padding: '6px 14px', fontSize: 13 }} disabled={sending || debating} onClick={() => send(chip)}>
                  {chip}
                </button>
              ))}
            </div>
          )}
          {plan?.degraded && (
            <div className="tiny" style={{ marginTop: 10, color: 'var(--warn, #b45309)' }}>
              ⚠️ 这轮用的是本地规则（模型暂时不可用），如果有听错的请直接纠正我。
            </div>
          )}
          <div style={{ display: 'flex', gap: 10, marginTop: 18 }}>
            <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }} placeholder="补充你的信息…" style={{ flex: 1, border: '1px solid var(--line)', background: 'var(--panel)', color: 'var(--ink)', borderRadius: 12, padding: '12px 14px', fontSize: 14 }} disabled={inputLocked} />
            <button className="btn" onClick={() => send()} disabled={sending || debating}>{debating ? '分析中…' : sending ? '发送中…' : '发送'}</button>
          </div>
          {debating && (
            <div className="card" style={{ marginTop: 14, padding: 14 }}>
              <div className="tiny" style={{ color: 'var(--ink3)', marginBottom: 8 }}>法庭开庭中…</div>
              {stages.length === 0 && <div className="tiny">正在准备材料…</div>}
              {stages.map((s) => (
                <div key={s.stage} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', padding: '4px 0' }}>
                  <span className="tiny" style={{ flex: '0 0 auto' }}>{s.status === 'done' ? '✅' : '⏳'}</span>
                  <span className="tiny" style={{ flex: 1 }}>
                    <b style={{ color: 'var(--ink)' }}>{STAGE_LABELS[s.stage] ?? s.stage}</b>
                    {s.summary ? ` · ${s.summary}` : ''}
                    {s.arguments?.length ? <span style={{ display: 'block', color: 'var(--ink3)' }}>{s.arguments.join('；')}</span> : null}
                  </span>
                </div>
              ))}
            </div>
          )}
          {(canDebate || isCompleted) && (
            <div style={{ marginTop: 16, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: 10 }}>
              {canDebate && plan?.can_stop && <span className="tiny" style={{ color: 'var(--ink3)' }}>信息已够，可以直接出判决书</span>}
              {isCompleted && <span className="tiny" style={{ color: 'var(--ink3)' }}>本案已生成判决书</span>}
              <button className="btn" onClick={() => (isCompleted ? navigate('/verdict/' + caseId) : debate())}>
                {isCompleted ? '查看判决书' : '启动辩论分析'}
              </button>
            </div>
          )}
        </div>
        <div className="card" style={{ alignSelf: 'start' }}>
          <h3 style={{ fontSize: 16 }}>信息收集进度</h3>
          <div className="tiny" style={{ margin: '6px 0 14px', color: 'var(--ink3)' }}>
            {(plan?.can_stop && missing.length > 0) ? '可先分析，另有 ' + missing.length + ' 项建议补充' : (missing.length === 0 ? '已收集完整' : '还需补充 ' + missing.length + ' 项')}
          </div>
          <ul className="fieldlist">
            {(missing.length === 0 ? [] : missing).map((f) => (<li key={f}>{fieldLabel(caseData?.case_type as string, f)}<span className="tiny">{plan?.can_stop ? '建议补充' : '待补充'}</span></li>))}
            {missing.length === 0 && <li className="ok">信息已补齐</li>}
          </ul>
          <div className="tiny" style={{ marginTop: 12, color: 'var(--ink3)' }}>核心信息齐了就能分析，其余可选</div>
        </div>
      </div>
    </div>
  );
}