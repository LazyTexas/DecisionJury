import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography, Spin, Button, Input, Space, Tag, Alert, Divider, Empty,
} from 'antd';
import {
  SendOutlined, ArrowLeftOutlined, RobotOutlined, UserOutlined, ThunderboltOutlined,
} from '@ant-design/icons';
import { Message, MessageRole, Case, CaseStatus, CaseType } from '../types';
import {
  getCaseDetail, getCaseMessages, sendMessage, startDebate, saveLocalMessages,
} from '../api';
import { CASE_STATUS_META, fieldLabel } from '../constants';
import { formatDateTime } from '../utils/format';
import ThinkingOverlay from '../components/ThinkingOverlay';

function roleAvatar(role: MessageRole) {
  switch (role) {
    case MessageRole.USER: return <UserOutlined style={{ fontSize: 18, color: '#1677ff' }} />;
    case MessageRole.ASSISTANT: return <RobotOutlined style={{ fontSize: 18, color: '#52c41a' }} />;
    case MessageRole.AGENT: return <ThunderboltOutlined style={{ fontSize: 18, color: '#faad14' }} />;
    default: return <RobotOutlined />;
  }
}

function roleName(role: MessageRole): string {
  switch (role) {
    case MessageRole.USER: return '你';
    case MessageRole.ASSISTANT: return '决策助手';
    case MessageRole.AGENT: return 'Agent';
    default: return '';
  }
}

function roleColor(role: MessageRole): string {
  switch (role) {
    case MessageRole.USER: return '#e6f4ff';
    case MessageRole.ASSISTANT: return '#f6ffed';
    case MessageRole.AGENT: return '#fffbe6';
    default: return '#fafafa';
  }
}

export default function ChatPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [sending, setSending] = useState(false);
  const [debating, setDebating] = useState(false);
  const [operateError, setOperateError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const sendingMsgIdRef = useRef<string | null>(null);

  // ---- time 类型护栏 ----
  // 后端辩论引擎当前只支持 shopping：time 案件若触发辩论会得到
  // UNSUPPORTED_CASE_TYPE 且案件卡在 debating（后端不回滚）。
  // 前端策略：辩论入口仅对 shopping 开放；存量 time 案件只读展示。
  const isTimeCase = caseData?.case_type === CaseType.TIME;
  // 只有「购物 + 收集完成 + 未被拒绝」的案件可以进入辩论
  const canDebate =
    caseData?.status === CaseStatus.READY_FOR_DEBATE && !isTimeCase;
  const isCompleted = caseData?.status === CaseStatus.COMPLETED;
  const isRejected = caseData?.status === CaseStatus.REJECTED;
  // 后端曾把案件置为 debating 但流程中断（time 死锁 / 刷新中断）
  const isStuckDebating = caseData?.status === CaseStatus.DEBATING;
  // 辩论中/已判决/已拒绝/发送中/time 未支持/卡死状态，输入一律禁用
  const inputDisabled =
    isCompleted || isRejected || canDebate || sending || debating || !caseData ||
    isTimeCase || isStuckDebating;

  /** 更新消息并同步持久化到 localStorage（真实模式下刷新恢复） */
  const commitMessages = (updater: (prev: Message[]) => Message[]) => {
    setMessages((prev) => {
      const next = updater(prev);
      if (caseId) saveLocalMessages(caseId, next);
      return next;
    });
  };

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    setLoading(true);
    Promise.all([getCaseDetail(caseId), getCaseMessages(caseId)])
      .then(([c, msgs]) => {
        if (cancelled) return;
        if (!c) { setLoadError('案件不存在'); return; }
        setCaseData(c);
        setMessages(msgs);
      })
      .catch((err) => { if (!cancelled) setLoadError(err.message || '加载失败'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [caseId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, sending, debating]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending || debating || !caseId || !caseData) return;
    if (isCompleted || isRejected || canDebate || isTimeCase || isStuckDebating) return;

    const userMsg: Message = {
      message_id: `user-${Date.now()}`,
      case_id: caseId,
      role: MessageRole.USER,
      content: text,
      created_at: new Date().toISOString(),
    };
    sendingMsgIdRef.current = userMsg.message_id;
    commitMessages((prev) => [...prev, userMsg]);

    setInput('');
    setSending(true);
    setOperateError(null);
    try {
      const res = await sendMessage(caseId, text);
      const assistantMsg: Message = {
        message_id: `reply-${Date.now()}`,
        case_id: caseId,
        role: MessageRole.ASSISTANT,
        content: res.reply,
        created_at: new Date().toISOString(),
      };
      commitMessages((prev) => [...prev, assistantMsg]);
      // 用后端返回的权威状态更新案件
      setCaseData((prev) => prev ? {
        ...prev,
        status: res.case_status as CaseStatus,
        collected_fields: res.collected_fields,
        missing_fields: res.missing_fields,
      } : prev);
    } catch (err: any) {
      // 请求失败：撤回刚追加的乐观用户消息，避免出现无回复的悬空气泡
      const failedId = sendingMsgIdRef.current;
      commitMessages((prev) =>
        failedId ? prev.filter((m) => m.message_id !== failedId) : prev);
      setOperateError(err?.message || '发送失败，请重试');
    } finally {
      sendingMsgIdRef.current = null;
      setSending(false);
    }
  };

  const handleStartDebate = async () => {
    if (!caseId || debating) return;
    setDebating(true);
    setOperateError(null);
    try {
      const res = await startDebate(caseId);
      setCaseData((prev) => prev ? {
        ...prev,
        status: res.case_status as CaseStatus,
        report_id: res.report?.report_id ?? prev.report_id,
      } : prev);
      navigate(`/verdict/${caseId}`);
    } catch (err: any) {
      const code = err?.code;
      if (code === 'MISSING_FIELDS') {
        setOperateError('信息收集尚未完整，已回到信息收集阶段。');
      } else {
        setOperateError(err?.message || '启动辩论失败，请稍后重试');
      }
      // 状态可能已被后端改变（如 MISSING_FIELDS → collecting），重新拉取
      try {
        const fresh = await getCaseDetail(caseId);
        if (fresh) setCaseData(fresh);
      } catch { /* 忽略刷新失败 */ }
    } finally {
      setDebating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey && !inputDisabled) {
      e.preventDefault();
      handleSend();
    }
  };

  // ---- 渲染 ----
  if (loading) {
    return <div style={{ textAlign: 'center', paddingTop: 120 }}><Spin size="large" /><p style={{ marginTop: 16, color: '#999' }}>加载中…</p></div>;
  }
  if (loadError) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Typography.Text type="danger">{loadError}</Typography.Text><br />
        <Button style={{ marginTop: 16 }} onClick={() => navigate('/')}>返回首页</Button>
      </div>
    );
  }
  if (!caseData) {
    return <Empty description="案件不存在" style={{ paddingTop: 120 }}><Button onClick={() => navigate('/')}>返回首页</Button></Empty>;
  }

  const statusMeta = CASE_STATUS_META[caseData.status];

  // 信息收集进度：仅购物案件有权威 missing_fields（后端对 time 不计算）
  const missingFields = caseData.missing_fields ?? [];
  const showCollectHint =
    caseData.status === CaseStatus.COLLECTING &&
    caseData.case_type === CaseType.SHOPPING &&
    missingFields.length > 0;

  // 头部状态标签：time 卡死案件用明确文案，避免"辩论中"误导
  const displayStatus = isStuckDebating && isTimeCase
    ? { label: '流程中断', color: 'error' }
    : statusMeta;

  const inputPlaceholder = isTimeCase
    ? '时间决策分析尚未上线，暂时无法继续'
    : isRejected
      ? '该决策已被系统拒绝，无法继续'
      : isCompleted
        ? '案件已判决，查看判决书了解结果'
        : canDebate
          ? '信息已收集完整，请开始辩论分析'
          : sending || debating
            ? '处理中…'
            : '补充你的情况，帮助助手收集完整信息…';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: 'calc(100vh - 104px)' }}>
      {/* 头部 */}
      <div style={{ marginBottom: 16 }}>
        <Space style={{ marginBottom: 8, cursor: 'pointer' }} onClick={() => navigate('/')}>
          <ArrowLeftOutlined />
          <Typography.Text type="secondary">返回首页</Typography.Text>
        </Space>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Typography.Title level={4} style={{ margin: 0 }}>{caseData.title}</Typography.Title>
          <Tag color={isCompleted ? 'success' : isRejected ? 'error' : displayStatus.color}>
            {isCompleted ? '已判决' : isRejected ? '已拒绝' : displayStatus.label}
          </Tag>
        </div>
      </div>

      {/* time 案件：后端暂不支持 → 自然降级提示，绝不暴露辩论入口 */}
      {isTimeCase && isStuckDebating && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="该案件的分析已中断"
          description="这是一条时间/日程决策记录，当前系统仅支持购物决策的完整分析。该案件无法继续或重试，你可以返回首页，新建一个购物决策来体验完整流程。"
          action={<Button size="small" onClick={() => navigate('/')}>返回首页</Button>}
        />
      )}
      {isTimeCase && !isStuckDebating && !isRejected && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="时间决策分析尚未上线"
          description="当前系统仅支持购物决策的完整分析。你可以查看此前的对话记录，或返回首页新建一个购物决策。"
          action={<Button size="small" onClick={() => navigate('/create')}>新建购物决策</Button>}
        />
      )}

      {/* 辩论状态兜底：案件处于 debating 但流程未在本页发起（刷新中断等） */}
      {!isTimeCase && isStuckDebating && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message="辩论分析进行中或已中断"
          description="后端正在同步执行多 Agent 辩论。为避免重复分析，请不要在本页重复操作；若长时间没有结果，请返回案件列表稍后刷新查看判决书。"
          action={<Button size="small" onClick={() => navigate('/')}>返回首页</Button>}
        />
      )}

      {/* 高风险拒绝提示 */}
      {isRejected && (
        <Alert
          type="error"
          showIcon
          style={{ marginBottom: 16 }}
          message="该决策超出系统支持范围"
          description="系统识别到该决策可能涉及高风险或专业领域（如医疗、投资、法律等），已停止分析。请勿继续输入，如需帮助可返回首页发起新的购物决策。"
          action={<Button size="small" onClick={() => navigate('/')}>返回首页</Button>}
        />
      )}

      {/* 信息收集进度提示 */}
      {showCollectHint && (
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="信息收集进行中"
          description={
            <Space wrap size={[4, 4]}>
              <Typography.Text type="secondary" style={{ fontSize: 13 }}>还需补充：</Typography.Text>
              {missingFields.map((f) => (
                <Tag key={f} color="blue" style={{ marginInlineEnd: 0 }}>
                  {fieldLabel(caseData.case_type, f)}
                </Tag>
              ))}
            </Space>
          }
        />
      )}

      {/* 消息列表 */}
      <div
        className="chat-messages"
        style={{
          flex: 1, overflowY: 'auto', padding: '16px 0', display: 'flex',
          flexDirection: 'column', gap: 16,
        }}
      >
        {messages.length === 0 && !sending && !debating && (
          <Empty
            style={{ paddingTop: 40 }}
            description={showCollectHint ? '开始补充第一条信息吧' : '暂无消息'}
          />
        )}

        {messages.map((msg) => (
          <div
            key={msg.message_id}
            style={{
              display: 'flex', flexDirection: msg.role === MessageRole.USER ? 'row-reverse' : 'row',
              gap: 12, alignItems: 'flex-start',
            }}
          >
            <div
              style={{
                width: 36, height: 36, borderRadius: '50%', background: roleColor(msg.role),
                display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0,
              }}
            >
              {roleAvatar(msg.role)}
            </div>
            <div
              style={{
                maxWidth: '75%', background: roleColor(msg.role), borderRadius: 12,
                padding: '12px 16px', border: '1px solid rgba(0,0,0,0.04)',
              }}
            >
              <Space size={8} style={{ marginBottom: 4 }}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                  {roleName(msg.role)}
                </Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 11 }}>
                  {formatDateTime(msg.created_at)}
                </Typography.Text>
              </Space>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.7 }}>{msg.content}</div>
            </div>
          </div>
        ))}

        {/* 真实异步状态卡（消息分析 / 辩论执行），非伪造流式动画 */}
        {sending && (
          <ThinkingOverlay active title="正在分析你的回答…" description="助手正在解析并更新案件信息，请稍候。" />
        )}
        {debating && (
          <ThinkingOverlay
            active
            title="正在执行多 Agent 辩论分析…"
            description="系统正在检索历史证据、调用成本分析工具，并组织正反方论证与法官裁决。该过程通常需要数十秒，请勿关闭页面或重复点击。"
          />
        )}

        {/* 操作失败提示 */}
        {operateError && !sending && !debating && (
          <Alert type="error" showIcon message={operateError} closable onClose={() => setOperateError(null)} />
        )}

        {/* 可启动辩论 */}
        {canDebate && !debating && (
          <Alert
            type="info"
            message={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>信息已收集完整，可以启动辩论分析</span>
                <Button type="primary" onClick={handleStartDebate}>启动辩论</Button>
              </div>
            }
            style={{ marginTop: 16 }}
          />
        )}

        {isCompleted && (
          <Alert
            type="success"
            message="判决书已生成"
            style={{ marginTop: 16 }}
            showIcon
            action={
              <Button size="small" type="primary" onClick={() => navigate(`/verdict/${caseId}`)}>
                查看判决书
              </Button>
            }
          />
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* 输入区 */}
      <Divider style={{ margin: '12px 0' }} />
      <div style={{ display: 'flex', gap: 8, padding: '8px 0' }}>
        <Input.TextArea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={inputPlaceholder}
          disabled={inputDisabled}
          rows={2}
          style={{ borderRadius: 8, resize: 'none' }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={sending}
          disabled={inputDisabled || !input.trim()}
          style={{ height: 'auto', borderRadius: 8 }}
        >
          发送
        </Button>
      </div>
    </div>
  );
}
