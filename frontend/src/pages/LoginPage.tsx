import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import AuthShell from '../auth/AuthShell';

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [id, setId] = useState('');
  const [pwd, setPwd] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;
  const from = (location.state as { from?: string } | null)?.from;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true); setError('');
    try {
      await login(id.trim(), pwd);
      navigate(from && from !== '/login' ? from : '/', { replace: true });
    } catch (err) { setError((err as Error).message || '登录失败，请重试'); }
    finally { setSubmitting(false); }
  };

  return (
    <AuthShell title="登录" subtitle="冷静决策助手，登录后继续你的决策旅程">
      <form onSubmit={submit}>
        <div className="field"><label>用户 ID</label><input value={id} onChange={(e) => setId(e.target.value)} placeholder="你的用户 ID（自定义，将用于关联案件）" maxLength={40} /></div>
        <div className="field"><label>密码</label><input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} placeholder="请输入密码" /></div>
        {error && <div className="auth-error">{error}</div>}
        <button className="btn" style={{ width: '100%' }} disabled={submitting}>{submitting ? '登录中…' : '登录'}</button>
      </form>
      <div className="auth-link">还没有账号？<Link to="/register">立即注册</Link></div>
    </AuthShell>
  );
}