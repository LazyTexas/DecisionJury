import { useCallback, useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography, Spin, Button, Input, Space, Tag, Alert, Divider, Empty,
} from 'antd';
import { SendOutlined, ArrowLeftOutlined, RobotOutlined, UserOutlined, ThunderboltOutlined } from '@ant-design/icons';
import { Message, MessageRole, Case, CaseStatus } from '../types';
import { getCaseDetail, getCaseMessages, sendMessage, startDebate } from '../api';
import { createMockChatStream, StreamStatus } from '../api/chat-stream';
import ThinkingOverlay from '../components/ThinkingOverlay';

const statusLabel: Record<CaseStatus, string> = {
  [CaseStatus.COLLECTING]: '信息收集',
  [CaseStatus.READY_FOR_DEBATE]: '待辩论',
  [CaseStatus.DEBATING]: '辩论中',
  [CaseStatus.COMPLETED]: '已判决',
  [CaseStatus.REJECTED]: '已拒绝',
  [CaseStatus.ARCHIVED]: '已归档',
};

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
  const [error, setError] = useState<string | null>(null);

  const [sending, setSending] = useState(false);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>('idle');
  const [replyHistory, setReplyHistory] = useState<string[]>([]);
  const [debating, setDebating] = useState(false);
  const streamRef = useRef<{ close: () => void } | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const canDebate = caseData?.status === CaseStatus.READY_FOR_DEBATE;
  const isCompleted = caseData?.status === CaseStatus.COMPLETED;

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;
    Promise.all([getCaseDetail(caseId), getCaseMessages(caseId)])
      .then(([c, msgs]) => {
        if (cancelled) return;
        if (!c) { setError('案件不存在'); return; }
        setCaseData(c);
        setMessages(msgs);
      })
      .catch((err) => { if (!cancelled) setError(err.message || '加载失败'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [caseId]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, replyHistory]);

  useEffect(() => {
    return () => streamRef.current?.close();
  }, []);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || sending || !caseId || !caseData) return;

    setSending(true);
    setInput('');
    setReplyHistory([]);
    setStreamStatus('sending');

    // 添加用户消息
    const userMsg: Message = {
      message_id: `user-${Date.now()}`,
      case_id: caseId,
      role: MessageRole.USER,
      content: text,
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    // 模拟流式回复
    streamRef.current = createMockChatStream(caseId, text, {
      onStatusChange: setStreamStatus,
      onReply: (reply) => setReplyHistory((prev) => [...prev, reply]),
      onDone: async () => {
        // 模拟调用后端 sendMessage
        try {
          const res = await sendMessage(caseId, text);
          // 追加助手消息
          const assistantMsg: Message = {
            message_id: `reply-${Date.now()}`,
            case_id: caseId,
            role: MessageRole.ASSISTANT,
            content: res.reply,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
          // 更新案件状态
          setCaseData((prev) => prev ? { ...prev, status: res.case_status as CaseStatus, missing_fields: res.missing_fields } : prev);

          // 如果还有缺失字段，追加追问
          if (res.missing_fields.length > 0) {
            const prompt: Message = {
              message_id: `prompt-${Date.now()}`,
              case_id: caseId,
              role: MessageRole.ASSISTANT,
              content: `还需要补充：${res.missing_fields.join('、')}`,
              created_at: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, prompt]);
          }
        } catch (err: any) {
          setError(err.message || '发送失败');
        } finally {
          setSending(false);
          setStreamStatus('completed');
        }
      },
      onError: (errMsg) => {
        setError(errMsg);
        setSending(false);
      },
    });
  }, [input, sending, caseId, caseData]);

  // 启动辩论
  const handleStartDebate = async () => {
    if (!caseId) return;
    setDebating(true);
    try {
      const res = await startDebate(caseId);
      setCaseData((prev) => prev ? { ...prev, status: res.case_status as CaseStatus, report_id: res.report.report_id } : prev);
      navigate(`/verdict/${caseId}`);
    } catch (err: any) {
      setError(err.message || '启动辩论失败');
    } finally {
      setDebating(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // render
  if (loading) {
    return <div style={{ textAlign: 'center', paddingTop: 120 }}><Spin size="large" /><p style={{ marginTop: 16, color: '#999' }}>加载中…</p></div>;
  }
  if (error) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Typography.Text type="danger">{error}</Typography.Text><br />
        <Button style={{ marginTop: 16 }} onClick={() => navigate('/')}>返回首页</Button>
      </div>
    );
  }
  if (!caseData) {
    return <Empty description="案件不存在" style={{ paddingTop: 120 }}><Button onClick={() => navigate('/')}>返回首页</Button></Empty>;
  }

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
          <Tag color={isCompleted ? 'success' : canDebate ? 'warning' : 'processing'}>
            {statusLabel[caseData.status]}
          </Tag>
        </div>
      </div>

      {/* 消息列表 */}
      <div className="chat-messages" style={{ flex: 1, overflowY: 'auto', padding: '16px 0', display: 'flex', flexDirection: 'column', gap: 16 }}>
        {messages.length === 0 && <Empty description="暂无消息" style={{ paddingTop: 40 }} />}

        {messages.map((msg) => (
          <div key={msg.message_id} style={{ display: 'flex', flexDirection: msg.role === MessageRole.USER ? 'row-reverse' : 'row', gap: 12, alignItems: 'flex-start' }}>
            <div style={{ width: 36, height: 36, borderRadius: '50%', background: roleColor(msg.role), display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0 }}>
              {roleAvatar(msg.role)}
            </div>
            <div style={{ maxWidth: '75%', background: roleColor(msg.role), borderRadius: 12, padding: '12px 16px', border: '1px solid rgba(0,0,0,0.04)' }}>
              <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                {roleName(msg.role)}
              </Typography.Text>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.7 }}>{msg.content}</div>
            </div>
          </div>
        ))}

        {/* 流式思考回复 */}
        <ThinkingOverlay status={streamStatus} replyHistory={replyHistory} />

        {/* 启动辩论按钮 */}
        {canDebate && (
          <Alert
            type="info"
            message={
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span>信息已收集完整，可以启动辩论分析了</span>
                <Button type="primary" loading={debating} onClick={handleStartDebate}>
                  启动辩论
                </Button>
              </div>
            }
            style={{ marginTop: 16 }}
          />
        )}

        {isCompleted && (
          <Alert type="success" message="判决书已生成" style={{ marginTop: 16 }} showIcon
            action={<Button size="small" type="primary" onClick={() => navigate(`/verdict/${caseId}`)}>查看判决书</Button>}
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
          placeholder={isCompleted || canDebate ? '信息已完整，等待启动辩论' : '输入你的回答…'}
          disabled={isCompleted || canDebate || sending}
          rows={2}
          style={{ borderRadius: 8, resize: 'none' }}
        />
        <Button
          type="primary" icon={<SendOutlined />} onClick={handleSend}
          loading={sending}
          disabled={isCompleted || canDebate || !input.trim() || sending}
          style={{ height: 'auto', borderRadius: 8 }}
        >
          发送
        </Button>
      </div>
    </div>
  );
}
