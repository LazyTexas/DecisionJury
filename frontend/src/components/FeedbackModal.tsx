import { useState } from 'react';
import { submitFeedback } from '../api';

const ACTIONS = [
  { v: 'bought', label: '买了 / 做了' },
  { v: 'not_bought', label: '没买 / 没做' },
  { v: 'delayed', label: '延后了' },
  { v: 'other', label: '其他' },
];

export default function FeedbackModal({
  caseId,
  open,
  onClose,
}: {
  caseId: string;
  open: boolean;
  onClose: () => void;
}) {
  const [action, setAction] = useState('bought');
  const [sat, setSat] = useState(3);
  const [review, setReview] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  if (!open) return null;

  const submit = async () => {
    setSubmitting(true); setError('');
    try {
      await submitFeedback(caseId, { actual_action: action, satisfaction: sat, review });
      onClose();
    } catch (e) { setError((e as Error).message || '提交失败'); }
    finally { setSubmitting(false); }
  };

  return (
    <div className="overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head"><h3>决策复盘</h3><button className="modal-x" aria-label="关闭" onClick={onClose}>×</button></div>
        <div className="field"><label>你最终做了什么？</label><select value={action} onChange={(e) => setAction(e.target.value)}>{ACTIONS.map((a) => <option key={a.v} value={a.v}>{a.label}</option>)}</select></div>
        <div className="field"><label>满意度评分</label><select value={sat} onChange={(e) => setSat(Number(e.target.value))}>{[5,4,3,2,1].map((n) => <option key={n} value={n}>{n} 分{n === 5 ? ' · 很满意' : n === 1 ? ' · 不满意' : ''}</option>)}</select></div>
        <div className="field"><label>复盘感想（选填）</label><textarea value={review} onChange={(e) => setReview(e.target.value)} placeholder="分享一下你的感受…" rows={3} /></div>
        {error && <div className="auth-error">{error}</div>}
        <button className="btn" style={{ width: '100%' }} onClick={submit} disabled={submitting}>{submitting ? '提交中…' : '提交复盘'}</button>
      </div>
    </div>
  );
}