import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getHistory, deleteHistory } from '../api';
import { CASE_TYPE_META, HISTORY_RESULT_META } from '../constants';
import { formatDate } from '../utils/format';
import { HistoryResult, CaseType } from '../types';
import type { HistoryItem } from '../types';

const FILTERS: { key: string; label: string }[] = [
  { key: 'all', label: '全部' }, { key: 'shopping', label: '购物' }, { key: 'time', label: '时间' }, { key: 'worth', label: '满意' }, { key: 'regret', label: '后悔' },
];
const typeIcon: Record<CaseType, string> = { [CaseType.SHOPPING]: '🛒', [CaseType.TIME]: '⏰' };
const resultIcon: Record<HistoryResult, string> = { [HistoryResult.WORTH]: '✓', [HistoryResult.REGRET]: '✕', [HistoryResult.NEUTRAL]: '·' };

export default function HistoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    getHistory({ page: 1, page_size: 100 })
      .then((res) => setItems(res.items))
      .catch(() => setItems([]))
      .finally(() => setLoading(false));
  }, []);

  const del = async (h: HistoryItem) => {
    setDeletingId(h.history_id);
    try { await deleteHistory(h.history_id); setItems((p) => p.filter((x) => x.history_id !== h.history_id)); }
    catch (e) { /* ignore */ }
    finally { setDeletingId(null); }
  };

  const shown = items.filter((h) => {
    if (filter === 'all') return true;
    if (filter === 'shopping' || filter === 'time') return h.case_type === filter;
    return h.result === filter;
  });

  return (
    <div>
      <div className="hero" style={{ paddingTop: 26 }}><h1 className="serif">决策历史记录</h1><p>回顾过往的决策与复盘。</p></div>
      <div className="grid2 hist">
        <div className="card" style={{ alignSelf: 'start' }}>
          <h3 style={{ fontSize: 16, marginBottom: 12 }}>筛选</h3>
          <div className="vfilter">
            {FILTERS.map((f) => (<button key={f.key} className={"chip" + (filter === f.key ? ' active' : '')} onClick={() => setFilter(f.key)}>{f.label}</button>))}
          </div>
        </div>
        <div className="h-list">
          {loading ? (<div className="card"><p className="muted">加载中…</p></div>) : shown.length === 0 ? (<div className="card"><p className="muted">暂无匹配记录。</p></div>) : (
            shown.map((h) => {
              const cat = CASE_TYPE_META[h.case_type]; const r = HISTORY_RESULT_META[h.result];
              return (
                <div key={h.history_id} className="h-card" onClick={() => (h.report_id ? navigate('/verdict/' + h.case_id) : h.case_id ? navigate('/chat/' + h.case_id) : null)}>
                  <button className="card-del" aria-label="删除记录" disabled={deletingId === h.history_id} onClick={(e) => { e.stopPropagation(); del(h); }}>×</button>
                  <div className="h-top"><span className="tag shop">{typeIcon[h.case_type]} {cat?.label ?? h.case_type}</span><span className="tag con">{resultIcon[h.result] ?? ''} {r?.label ?? h.result}</span></div>
                  <b>{h.title}</b><p>{h.summary}</p>
                  <div className="tiny" style={{ marginTop: 6, color: 'var(--ink3)' }}>{formatDate(h.created_at)}</div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}