// ============================================================
// 登录 / 注册页共用外壳：居中卡片 + 品牌标题
// ============================================================

import { Card, Typography } from 'antd';
import type { ReactNode } from 'react';

export default function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
}) {
  return (
    <div
      style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: '#f5f5f5',
        padding: 24,
      }}
    >
      <Card style={{ width: 400, borderRadius: 12 }} styles={{ body: { padding: '32px 36px' } }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <Typography.Title level={3} style={{ marginBottom: 4 }}>
            DecisionJury
          </Typography.Title>
          {title && (
            <Typography.Title level={5} type="secondary" style={{ margin: 0 }}>
              {title}
            </Typography.Title>
          )}
          {subtitle && (
            <Typography.Paragraph type="secondary" style={{ marginTop: 8, fontSize: 13 }}>
              {subtitle}
            </Typography.Paragraph>
          )}
        </div>
        {children}
      </Card>
    </div>
  );
}
