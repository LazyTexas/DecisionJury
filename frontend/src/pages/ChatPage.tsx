import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography,
  Spin,
  Button,
  Input,
  Space,
  Tag,
  Alert,
  Divider,
  Empty,
} from 'antd';
import {
  ArrowLeftOutlined,
  SendOutlined,
  RobotOutlined,
  UserOutlined,
  SwapOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { Message, MessageRole, SessionStage, Case } from '../types';
import { getCaseDetail, getSessionMessages, sendMessage } from '../api';

const stageLabel: Record<SessionStage, string> = {
  [SessionStage.INFO_COLLECTION]: '信息收集',
  [SessionStage.PRO_DEBATE]: '正方辩论',
  [SessionStage.CON_DEBATE]: '反方辩论',
  [SessionStage.JUDGE_RULING]: '法官裁决',
  [SessionStage.COMPLETED]: '已完成',
};

function roleAvatar(role: MessageRole) {
  switch (role) {
    case MessageRole.USER:
      return <UserOutlined style={{ fontSize: 18, color: '#1677ff' }} />;
    case MessageRole.ASSISTANT:
      return <RobotOutlined style={{ fontSize: 18, color: '#52c41a' }} />;
    case MessageRole.PRO_AGENT:
      return <ThunderboltOutlined style={{ fontSize: 18, color: '#faad14' }} />;
    case MessageRole.CON_AGENT:
      return <SwapOutlined style={{ fontSize: 18, color: '#ff4d4f' }} />;
    case MessageRole.JUDGE:
      return <SwapOutlined style={{ fontSize: 18, color: '#722ed1' }} />;
    default:
      return <RobotOutlined />;
  }
}

function roleName(role: MessageRole): string {
  switch (role) {
    case MessageRole.USER: return '你';
    case MessageRole.ASSISTANT: return '决策助手';
    case MessageRole.PRO_AGENT: return '正方 Agent';
    case MessageRole.CON_AGENT: return '反方 Agent';
    case MessageRole.JUDGE: return '法官 Agent';
    default: return '';
  }
}

function roleColor(role: MessageRole): string {
  switch (role) {
    case MessageRole.USER: return '#e6f4ff';
    case MessageRole.ASSISTANT: return '#f6ffed';
    case MessageRole.PRO_AGENT: return '#fffbe6';
    case MessageRole.CON_AGENT: return '#fff2f0';
    case MessageRole.JUDGE: return '#f9f0ff';
    default: return '#fafafa';
  }
}

export default function ChatPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [caseData, setCaseData] = useState<Case | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [stage, setStage] = useState<SessionStage>(SessionStage.INFO_COLLECTION);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  // 加载案件和会话数据
  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;

    Promise.all([
      getCaseDetail(caseId),
      getSessionMessages(caseId), // mock 中用 caseId 作为 sessionId 的 key
    ])
      .then(([caseInfo, msgs]) => {
        if (cancelled) return;
        if (!caseInfo) {
          setError('案件不存在');
          return;
        }
        setCaseData(caseInfo);
        setMessages(msgs);
        setStage(caseInfo.currentStage);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || '加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [caseId]);

  // 自动滚到底部
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || sending || !caseData) return;

    setSending(true);
    setInput('');

    try {
      const res = await sendMessage(caseData.sessionId, text);
      // 追加用户消息 + 助手回复
      setMessages((prev) => [...prev, res.userMessage, ...res.assistantMessages]);
      setStage(res.currentStage);

      // 如果对话完成，自动跳转到判决书页（延迟一点让用户看到最后的法官消息）
      if (res.isCompleted) {
        setTimeout(() => {
          navigate(`/verdict/${caseId}`);
        }, 3000);
      }
    } catch (err: any) {
      setInput(text); // 恢复输入
      setError(err.message || '发送失败');
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  // ---- 渲染 ----

  if (loading) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Spin size="large" />
        <p style={{ marginTop: 16, color: '#999' }}>加载对话中…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Typography.Text type="danger">{error}</Typography.Text>
        <br />
        <Button style={{ marginTop: 16 }} onClick={() => navigate('/')}>返回首页</Button>
      </div>
    );
  }

  if (!caseData) {
    return (
      <Empty description="案件不存在" style={{ paddingTop: 120 }}>
        <Button onClick={() => navigate('/')}>返回首页</Button>
      </Empty>
    );
  }

  const isCompleted = stage === SessionStage.COMPLETED;

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
          <Tag color={isCompleted ? 'success' : 'processing'}>{stageLabel[stage]}</Tag>
        </div>
      </div>

      {/* 消息列表 */}
      <div
        className="chat-messages"
        style={{
          flex: 1,
          overflowY: 'auto',
          padding: '16px 0',
          display: 'flex',
          flexDirection: 'column',
          gap: 16,
        }}
      >
        {messages.length === 0 && (
          <Empty description="暂无消息" style={{ paddingTop: 40 }} />
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            style={{
              display: 'flex',
              flexDirection: msg.role === MessageRole.USER ? 'row-reverse' : 'row',
              gap: 12,
              alignItems: 'flex-start',
            }}
          >
            {/* 头像 */}
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: '50%',
                background: roleColor(msg.role),
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                flexShrink: 0,
              }}
            >
              {roleAvatar(msg.role)}
            </div>

            {/* 气泡 */}
            <div
              style={{
                maxWidth: '75%',
                background: roleColor(msg.role),
                borderRadius: 12,
                padding: '12px 16px',
                border: '1px solid rgba(0,0,0,0.04)',
              }}
            >
              <Typography.Text
                type="secondary"
                style={{ fontSize: 12, display: 'block', marginBottom: 4 }}
              >
                {roleName(msg.role)}
                {msg.metadata?.agentName ? ` · ${msg.metadata.agentName}` : ''}
              </Typography.Text>
              <div style={{ whiteSpace: 'pre-wrap', fontSize: 14, lineHeight: 1.7 }}>
                {msg.content}
              </div>
              {msg.metadata?.confidence !== undefined && (
                <div style={{ marginTop: 8 }}>
                  <Tag style={{ fontSize: 11 }}>
                    置信度: {Math.round(msg.metadata.confidence * 100)}%
                  </Tag>
                </div>
              )}
            </div>
          </div>
        ))}

        {isCompleted && (
          <Alert
            type="success"
            message="辩论已完成，即将跳转到判决书……"
            style={{ marginTop: 16 }}
            showIcon
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
          placeholder={isCompleted ? '对话已结束' : '输入你的回答或想法…'}
          disabled={isCompleted || sending}
          rows={2}
          style={{ borderRadius: 8, resize: 'none' }}
        />
        <Button
          type="primary"
          icon={<SendOutlined />}
          onClick={handleSend}
          loading={sending}
          disabled={isCompleted || !input.trim()}
          style={{ height: 'auto', borderRadius: 8 }}
        >
          发送
        </Button>
      </div>
    </div>
  );
}
