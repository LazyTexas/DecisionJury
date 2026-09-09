// ============================================================
// 观察清单 · 冷静期提醒
// 接后端 GET /api/watchlist，前端做到期高亮/置顶 + 待复盘徽标 + 倒计时。
// ============================================================

import { useEffect, useMemo, useState } from 'react';
import { getWatchlist, deleteWatchlistItem } from '../api';
import type { WatchlistItem } from '../types';

interface Enriched extends WatchlistItem { days: number; expired: boolean; }

function fmtDate(iso: string | undefined | null): string {
  if (!iso) return '—';
  const d = new Date(iso);
  return d.getFullYear() + '-' + ('0' + (d.getMonth() + 1)).slice(-2) + '-' + ('0' + d.getDate()).slice(-2);
}

export default function WatchlistPage() {
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getWatchlist()
      .then((res) => { if (!cancelled) setItems(res.items); })
      .catch(() => { if (!cancelled) setItems([]); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  const enriched = useMemo<Enriched[]>(() => {
    const now = Date.now();
    const list: Enriched[] = items.map((w) => {
      const due = w.due_at ? new Date(w.due_at).getTime() : NaN;
      const days = Number.isNaN(due) ? 0 : Math.ceil((due - now) / 86400000);
      const expired = w.status === 'waiting' && !Number.isNaN(due) && due <= now;
      return { ...w, days, expired };
    });
    // 到期未复盘置顶 → 未到期按剩余天数升序 → 已复盘在后
    return list.sort((a, b) => {
      const ka = a.expired ? 0 : a.status === 'waiting' ? 1 : 2;
      const kb = b.expired ? 0 : b.status === 'waiting' ? 1 : 2;
      if (ka !== kb) return ka - kb;
      if (ka === 1) return a.days - b.days;
      return 0;
    });
  }, [items]);

  const pending = enriched.filter((w) => w.expired).length;

  const del = async (w: WatchlistItem) => {
    if (!w.reminder_id) return;
    setDeletingId(w.reminder_id); setError(null);
    try { await deleteWatchlistItem(w.reminder_id); setItems((p) => p.filter((x) => x.reminder_id !== w.reminder_id)); }
    catch (e) { setError((e as Error).message || '删除失败，请重试'); }
    finally { setDeletingId(null); }
  };

  return (
    <div>
      <div className="wl-head">
        <h2>观察清单 · 冷静期</h2>
        <span className="count-badge"><span className="num">{pending}</span>待复盘</span>
      </div>

      {error && (<div className="card" style={{ marginBottom: 16, borderColor: 'var(--con)', background: 'color-mix(in srgb,var(--con) 8%,var(--panel))' }}><p style={{ color: 'var(--con)' }}>{error}</p></div>)}

      {loading ? (
        <div className="card"><p className="muted">加载中…</p></div>
      ) : enriched.length === 0 ? (
        <div className="card"><p className="muted">暂无观察项。</p></div>
      ) : (
        <div className="wl-list">
          {enriched.map((w) => {
            let ico: string, color: string, when: string, tag: string, cls = '';
            if (w.expired) { ico = '!'; color = 'var(--con)'; cls = 'due'; when = '已逾期 ' + (-w.days) + ' 天'; tag = '<span class="w-tag due">该复盘了</span>'; }
            else if (w.days <= 2) { ico = '⌛'; color = 'var(--gold)'; cls = 'near'; when = '还剩 ' + w.days + ' 天'; tag = '<span class="w-tag near">即将到期</span>'; }
            else if (w.status === 'reviewed') { ico = '✓'; color = 'var(--pro)'; when = '已复盘'; tag = '<span class="w-tag ok">已复盘</span>'; }
            else { ico = '⏳'; color = 'var(--tool)'; when = '还剩 ' + w.days + ' 天 冷静期'; tag = '<span class="w-tag near">冷静中</span>'; }
            return (
              <div key={w.case_id} className={'w-card ' + cls}>
                {w.reminder_id && <button className="card-del" aria-label="删除提醒" disabled={deletingId === w.reminder_id} onClick={(e) => { e.stopPropagation(); del(w); }}>×</button>}
                <div className="w-ico" style={{ background: color }}>{ico}</div>
                <div className="w-body">
                  <div className="w-title">{w.title} <span dangerouslySetInnerHTML={{ __html: tag }} /></div>
                  <div className="w-reason">{w.reason}</div>
                  <div className="tiny">到期：{fmtDate(w.due_at)}</div>
                </div>
                <div className="w-when" style={{ color }}>{when}</div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}