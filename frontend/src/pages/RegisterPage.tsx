import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import AuthShell from '../auth/AuthShell';

export default function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [uid, setUid] = useState('');
  const [name, setName] = useState('');
  const [pwd, setPwd] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/" replace />;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^[a-zA-Z0-9_-]{2,40}$/.test(uid.trim())) { setError('用户 ID 需 2-40 位，仅支持字母、数字、下划线、中划线'); return; }
    if (pwd.length < 6) { setError('密码至少 6 位'); return; }
    if (pwd !== confirm) { setError('两次输入的密码不一致'); return; }
    setSubmitting(true); setError('');
    try {
      await register(uid.trim(), name.trim() || uid.trim(), pwd);
      navigate('/', { replace: true });
    } catch (err) { setError((err as Error).message || '注册失败，请重试'); }
    finally { setSubmitting(false); }
  };

  return (
    <AuthShell title="注册" subtitle="选择一个用户 ID，注册后即刻开始冷静决策">
      <form onSubmit={submit}>
        <div className="field"><label>用户 ID</label><input value={uid} onChange={(e) => setUid(e.target.value)} placeholder="如：alice_2024" maxLength={40} /><div className="tiny" style={{ marginTop: 6, color: 'var(--ink3)' }}>用户 ID 唯一，登录与案件归属都使用它</div></div>
        <div className="field"><label>昵称（选填）</label><input value={name} onChange={(e) => setName(e.target.value)} placeholder="展示用昵称，默认同用户 ID" maxLength={20} /></div>
        <div className="field"><label>密码</label><input type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} placeholder="至少 6 位" /></div>
        <div className="field"><label>确认密码</label><input type="password" value={confirm} onChange={(e) => setConfirm(e.target.value)} placeholder="再次输入密码" /></div>
        {error && <div className="auth-error">{error}</div>}
        <button className="btn" style={{ width: '100%' }} disabled={submitting}>{submitting ? '注册中…' : '注册并登录'}</button>
      </form>
      <div className="auth-link">已有账号？<Link to="/login">去登录</Link></div>
    </AuthShell>
  );
}