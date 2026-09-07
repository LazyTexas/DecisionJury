import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { createCase, appendLocalAssistantMessage, isMockMode } from '../api';
import { CaseType } from '../types';

export default function CreateCasePage() {
  const navigate = useNavigate();
  const [caseType, setCaseType] = useState<CaseType>(CaseType.SHOPPING);
  const [title, setTitle] = useState('');
  const [desc, setDesc] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const submit = async () => {
    if (!title.trim()) { alert('请填写决策标题'); return; }
    setSubmitting(true);
    try {
      const res = await createCase({ case_type: caseType, title, description: desc });
      if (res.case_id && res.next_question && !isMockMode) appendLocalAssistantMessage(res.case_id, res.next_question);
      navigate('/chat/' + res.case_id);
    } catch (err) { alert((err as Error).message || '创建失败，请重试'); }
    finally { setSubmitting(false); }
  };

  return (
    <div>
      <div className="hero" style={{ paddingTop: 26 }}><h1 className="serif">新建决策</h1><p>描述你正在纠结的决策，系统会通过多轮对话帮你理清思路，最终生成一份「决策判决书」。</p></div>
      <div className="card form-card">
        <div className="field"><label>决策类型</label><div className="type-opt">
          <div className={"opt" + (caseType === CaseType.SHOPPING ? ' sel' : '')} onClick={() => setCaseType(CaseType.SHOPPING)}><b>🛒 购物决策</b><span>买不买某个商品</span></div>
          <div className="opt disabled" title="即将开放"><b>⏰ 时间决策</b><span>要不要参加 / 投入某件事</span><span className="soon-badge">即将开放</span></div>
        </div></div>
        <div className="field"><label>决策标题</label><input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="例：是否购买降噪耳机" maxLength={60} /></div>
        <div className="field"><label>详细描述</label><textarea value={desc} onChange={(e) => setDesc(e.target.value)} placeholder="说说你在纠结什么？有哪些选择？你的顾虑是什么？" /></div>
        <div style={{ display: 'flex', gap: 12 }}><button className="btn" onClick={submit} disabled={submitting}>{submitting ? '提交中…' : '提交决策'}</button><button className="btn ghost" onClick={() => navigate('/')}>取消</button></div>
      </div>
    </div>
  );
}