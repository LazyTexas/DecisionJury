import { useEffect, useRef } from 'react';
import { Card, Typography, Space, Spin } from 'antd';
import { LoadingOutlined, CheckCircleOutlined, MessageOutlined } from '@ant-design/icons';
import { StreamStatus } from '../api/chat-stream';

interface ThinkingOverlayProps {
  status: StreamStatus;
  replyHistory: string[];
}

export default function ThinkingOverlay({ status, replyHistory }: ThinkingOverlayProps) {
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [replyHistory]);

  if (status === 'idle' || status === 'completed') return null;

  return (
    <Card
      size="small"
      style={{
        borderRadius: 8,
        background: '#fafafa',
        border: '1px solid #e8e8e8',
        marginBottom: 16,
      }}
    >
      <Space style={{ marginBottom: 12 }}>
        <Spin indicator={<LoadingOutlined spin />} />
        <Typography.Text strong style={{ color: '#1677ff' }}>
          {status === 'sending' ? '正在发送…' : '决策助手正在思考'}
        </Typography.Text>
      </Space>

      {replyHistory.map((text, i) => (
        <div key={i} style={{ display: 'flex', gap: 8, marginBottom: 6, alignItems: 'flex-start' }}>
          <CheckCircleOutlined style={{ color: '#52c41a', marginTop: 4 }} />
          <Typography.Text style={{ fontSize: 13, whiteSpace: 'pre-wrap' }}>{text}</Typography.Text>
        </div>
      ))}

      {status === 'streaming' && (
        <Space>
          <MessageOutlined style={{ color: '#1677ff' }} />
          <Typography.Text type="secondary" style={{ fontSize: 13 }} italic>
            正在生成回复…
          </Typography.Text>
        </Space>
      )}
      <div ref={endRef} />
    </Card>
  );
}
