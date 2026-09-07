// ============================================================
// 新版侧栏布局：品牌 + 导航 + 底部说明；顶部条含主题切换 + 适配用户名。
// 案件页（对话/判决书）按 caseId 从首页进入，不作顶层导航。
// ============================================================

import { useEffect, useMemo, useState } from 'react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import type { ReactNode } from 'react';
import { useTheme, ThemeIcon } from '../theme/ThemeContext';
import { useAuth } from '../auth/AuthContext';
import { getWatchlist } from '../api';
import type { WatchlistItem } from '../types';

const NAV = [
  { to: '/', label: '决策台', end: true, icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 10.5 12 3l9 7.5M5 9.5V21h14V9.5" /></svg> },
  { to: '/create', label: '新建决策', end: false, icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M12 5v14M5 12h14" /></svg> },
  { to: '/history', label: '历史记录', end: false, icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 6h16M4 12h16M4 18h10" /></svg> },
  { to: '/watchlist', label: '观察清单', end: false, icon: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg> },
];

const TITLES: Record<string, string> = {
  '/': '冷静决策，理性权衡',
  '/create': '新建决策',
  '/history': '决策历史记录',
  '/watchlist': '观察清单 · 冷静期',
};

function collapseIcon(): ReactNode {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><path d="M11 17l-5-5 5-5M18 17l-5-5 5-5" /></svg>;
}
function expandIcon(): ReactNode {
  return <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="15" height="15"><path d="M6 17l5-5-5-5M13 17l5-5-5-5" /></svg>;
}

function pendingCount(items: WatchlistItem[]): number {
  const now = Date.now();
  return items.filter((w) => w.status === 'waiting' && w.due_at && new Date(w.due_at).getTime() <= now).length;
}

export default function AppLayout() {
  const { theme, toggle } = useTheme();
  const { user } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [collapsed, setCollapsed] = useState(false);
  const [pending, setPending] = useState(0);
  const [noticeDismissed, setNoticeDismissed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getWatchlist()
      .then((res) => { if (!cancelled) setPending(pendingCount(res.items)); })
      .catch(() => { });
    return () => { cancelled = true; };
  }, []);

  const title = useMemo(() => {
    if (location.pathname.startsWith('/chat')) return '信息收集';
    if (location.pathname.startsWith('/verdict')) return '判决书';
    return TITLES[location.pathname] ?? 'DecisionJury';
  }, [location.pathname]);

  const displayName = user?.name || user?.user_id || '访客';

  return (
    <div className={'app-shell' + (collapsed ? ' collapsed' : '')}>
      <aside className="sidebar">
        <div className="s-top">
          <NavLink to="/" className="brand">
            <span className="logo">D</span>
            <span><b>DecisionJury</b><span>冷静决策台</span></span>
          </NavLink>
          <button className="collapse-btn" title={collapsed ? '展开侧栏' : '收起侧栏'} aria-label="收起侧栏" onClick={() => setCollapsed((c) => !c)}>
            {collapsed ? expandIcon() : collapseIcon()}
          </button>
        </div>

        <nav className="s-nav">
          {NAV.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => (isActive ? 'active' : '')}>
              <span className="ic">{item.icon}</span>
              <span className="txt">{item.label}</span>
              {item.to === '/watchlist' && pending > 0 && <span className="badge">{pending}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="s-foot">
          <div className="note">仅处理购物/时间等<b>低风险日常决策</b>，不涉及医疗、投资、法律等高风险领域。</div>
        </div>
      </aside>

      <div className="main">
        <div className="topbar">
          <div className="tb-title">{title}<span className="muted">DecisionJury · 多 Agent 冷静决策助手</span></div>
          <div className="tb-right">
            <button className="theme-btn" onClick={toggle} title="切换深色/浅色" aria-label="切换主题"><ThemeIcon theme={theme} /></button>
            <div className="user" title="当前用户">
              <span className="u-av">{displayName.slice(0, 1).toUpperCase()}</span>
              <span className="u-name">{displayName}</span>
            </div>
          </div>
        </div>

        <div className="content">
          {pending > 0 && !noticeDismissed && (
            <div className="notice">
              <span className="n-ico">!</span>
              <span className="n-text">你有 <b>{pending}</b> 条冷静期已到期，该复盘了。</span>
              <button className="n-btn" onClick={() => navigate('/watchlist')}>查看观察清单</button>
              <button className="n-x" aria-label="关闭" onClick={() => setNoticeDismissed(true)}>×</button>
            </div>
          )}
          <Outlet />
        </div>
      </div>
    </div>
  );
}