import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCaseList, getHistory, deleteCase, clearLocalMessages } from '../api';
import { CASE_STATUS_META, CASE_TYPE_META, HISTORY_RESULT_META } from '../constants';
import { formatDate } from '../utils/format';
import { CaseType, CaseStatus, HistoryResult } from '../types';
import type { CaseSummary, HistoryItem } from '../types';

const typeIcon: Record<CaseType, string> = { [CaseType.SHOPPING]: '🛒', [CaseType.TIME]: '⏰' };
const resultIcon: Record<HistoryResult, string> =
  { [HistoryResult.WORTH]: '✓', [HistoryResult.REGRET]: '✕', [HistoryResult.NEUTRAL]: '·' };

export default function HomePage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    Promise.all([getCaseList(), getHistory({ page: 1, page_size: 5 })])
      .then(([c, h]) => { setCases(c.items); setHistoryItems(h.items); })
      .catch((err) => setError(err.message || '加载失败'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const open = (c: CaseSummary) => {
    if (c.has_report || c.status === CaseStatus.COMPLETED) navigate('/verdict/' + c.case_id);
    else navigate('/chat/' + c.case_id);
  };

  const del = async (c: CaseSummary) => {
    setDeletingId(c.case_id);
    try {
      await deleteCase(c.case_id);
      clearLocalMessages(c.case_id);
      setCases((p) => p.filter((x) => x.case_id !== c.case_id));
    } catch (e) { setError((e as Error).message || '删除失败'); }
    finally { setDeletingId(null); }
  };

  return (
    <div>
      <div className="hero">
        <h1 className="serif">让每一次冲动，都先冷静一下</h1>
        <p>提交你的购物或时间决策，系统会检索历史证据、核算成本，并让正反双方理性对垒、由法官给出可解释的建议。</p>
        <div className="hero-actions"><button className="btn" onClick={() => navigate('/create')}>＋ 新建决策</button></div>
      </div>

      <div className="section-head"><h2>我的决策</h2><span className="tiny">共 {cases.length} 个</span></div>
      {loading ? (
        <div className="card"><p className="muted">加载中…</p></div>
      ) : error ? (
        <div className="card"><p className="muted" style={{ color: 'var(--con)' }}>{error}</p></div>
      ) : cases.length === 0 ? (
        <div className="card"><p className="muted">还没有决策案件，点击右上角「新建决策」开始。</p></div>
      ) : (
        <div className="case-list">
          {cases.map((c) => {
            const cat = CASE_TYPE_META[c.case_type];
            const st = CASE_STATUS_META[c.status];
            return (
              <div key={c.case_id} className="case-card" onClick={() => open(c)}>
                <button className="card-del" aria-label="删除决策" disabled={deletingId === c.case_id} onClick={(e) => { e.stopPropagation(); del(c); }}>×</button>
                <div className="case-top">
                  <span className="tag shop" style={{ background: cat?.color === 'orange' ? 'var(--brand-soft)' : undefined }}>{typeIcon[c.case_type]} {cat?.label ?? c.case_type}</span>
                  <span className="tag gold">{st?.label ?? c.status}</span>
                </div>
                <h3>{c.title}</h3>
                <p>{c.description}</p>
                <div className="case-foot"><span className="stage">· {c.message_count} 条消息</span><span className="tiny">{formatDate(c.updated_at)}</span></div>
              </div>
            );
          })}
        </div>
      )}

      <div className="section-head"><h2>决策历史记录</h2><span className="tiny" onClick={() => navigate('/history')}>查看全部 →</span></div>
      {historyItems.length === 0 ? (
        <div className="card"><p className="muted">暂无历史记录</p></div>
      ) : (
        <div className="h-list">
          {historyItems.map((h) => {
            const r = HISTORY_RESULT_META[h.result];
            const cat = CASE_TYPE_META[h.case_type];
            return (
              <div key={h.history_id} className="h-card" onClick={() => (h.report_id ? navigate('/verdict/' + h.case_id) : h.case_id ? navigate('/chat/' + h.case_id) : null)}>
                <div className="h-top"><span className="tag shop">{typeIcon[h.case_type]} {cat?.label ?? h.case_type}</span><span className="tag con">{resultIcon[h.result] ?? ''} {r?.label ?? h.result}</span></div>
                <b>{h.title}</b><p>{h.summary}</p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}