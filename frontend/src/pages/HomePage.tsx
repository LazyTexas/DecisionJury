import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Tag, Typography, Empty, Spin, Row, Col } from 'antd';
import {
  ShoppingCartOutlined,
  ClockCircleOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { CaseSummary, CaseType, CaseStatus } from '../types';
import { getCaseList } from '../api';

const caseTypeConfig: Record<CaseType, { label: string; color: string; icon: React.ReactNode }> = {
  [CaseType.SHOPPING]: { label: '购物', color: 'blue', icon: <ShoppingCartOutlined /> },
  [CaseType.TIME]: { label: '时间决策', color: 'orange', icon: <ClockCircleOutlined /> },
};

const statusLabel: Record<CaseStatus, string> = {
  [CaseStatus.COLLECTING]: '信息收集中',
  [CaseStatus.READY_FOR_DEBATE]: '待辩论',
  [CaseStatus.DEBATING]: '辩论中',
  [CaseStatus.COMPLETED]: '已判决',
  [CaseStatus.REJECTED]: '已拒绝',
  [CaseStatus.ARCHIVED]: '已归档',
};

const statusColor: Record<CaseStatus, string> = {
  [CaseStatus.COLLECTING]: 'processing',
  [CaseStatus.READY_FOR_DEBATE]: 'default',
  [CaseStatus.DEBATING]: 'warning',
  [CaseStatus.COMPLETED]: 'success',
  [CaseStatus.REJECTED]: 'error',
  [CaseStatus.ARCHIVED]: 'default',
};

export default function HomePage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCaseList()
      .then((data) => {
        if (!cancelled) setCases(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || '加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Spin size="large" />
        <p style={{ marginTop: 16, color: '#999' }}>加载中…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Typography.Text type="danger">{error}</Typography.Text>
      </div>
    );
  }

  if (cases.length === 0) {
    return (
      <Empty style={{ paddingTop: 120 }} description="还没有任何决策案件">
        <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
          点击右上角「新建决策」开始你的第一个冷静决策
        </Typography.Text>
      </Empty>
    );
  }

  return (
    <div>
      <Typography.Title level={3} style={{ marginBottom: 24 }}>
        我的决策案件
      </Typography.Title>
      <Row gutter={[16, 16]}>
        {cases.map((c) => {
          const cat = caseTypeConfig[c.case_type];
          const st = statusColor[c.status];
          return (
            <Col xs={24} sm={12} key={c.case_id}>
              <Card
                hoverable
                onClick={() => {
                  if (c.status === CaseStatus.COMPLETED || c.has_report) {
                    navigate(`/verdict/${c.case_id}`);
                  } else {
                    navigate(`/chat/${c.case_id}`);
                  }
                }}
                style={{ borderRadius: 8 }}
              >
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  <div>
                    <Tag icon={cat.icon} color={cat.color}>{cat.label}</Tag>
                    <Tag color={st}>{statusLabel[c.status]}</Tag>
                  </div>
                  <Typography.Text strong style={{ fontSize: 16 }}>
                    {c.title}
                  </Typography.Text>
                  <Typography.Paragraph
                    type="secondary"
                    ellipsis={{ rows: 2 }}
                    style={{ margin: 0, fontSize: 13 }}
                  >
                    {c.description}
                  </Typography.Paragraph>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                      {c.message_count} 条消息 · {new Date(c.updated_at).toLocaleDateString('zh-CN')}
                    </Typography.Text>
                    <RightOutlined style={{ color: '#ccc', fontSize: 12 }} />
                  </div>
                </div>
              </Card>
            </Col>
          );
        })}
      </Row>
    </div>
  );
}
