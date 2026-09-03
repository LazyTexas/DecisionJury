// ============================================================
// 分析过程状态卡
// 用于展示真实的异步等待状态（消息分析 / 辩论执行）。
// 后端无 SSE，无法推送逐步进度，这里只做如实文案 + loading，
// 不做伪造的"流式思考"动画。
// ============================================================

import { Card, Typography, Space, Spin } from 'antd';
import { LoadingOutlined } from '@ant-design/icons';

interface ThinkingOverlayProps {
  /** 是否可见（有异步任务在跑） */
  active: boolean;
  title?: string;
  description?: string;
}

export default function ThinkingOverlay({ active, title, description }: ThinkingOverlayProps) {
  if (!active) return null;

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
      <Space direction="vertical" size={4} style={{ width: '100%' }}>
        <Space>
          <Spin indicator={<LoadingOutlined spin />} />
          <Typography.Text strong style={{ color: '#1677ff' }}>
            {title ?? '处理中…'}
          </Typography.Text>
        </Space>
        {description && (
          <Typography.Text type="secondary" style={{ fontSize: 13 }}>
            {description}
          </Typography.Text>
        )}
      </Space>
    </Card>
  );
}
