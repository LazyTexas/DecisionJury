import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Tag, Typography, Empty, Spin, Row, Col } from 'antd';
import {
  ShoppingCartOutlined,
  ClockCircleOutlined,
  UserOutlined,
  TeamOutlined,
  DollarOutlined,
  QuestionCircleOutlined,
  RightOutlined,
} from '@ant-design/icons';
import { CaseSummary, DecisionCategory, CaseStatus } from '../types';
import { getCaseList } from '../api';

const categoryIcon: Record<DecisionCategory, React.ReactNode> = {
  [DecisionCategory.SHOPPING]: <ShoppingCartOutlined />,
  [DecisionCategory.TIME]: <ClockCircleOutlined />,
  [DecisionCategory.CAREER]: <UserOutlined />,
  [DecisionCategory.RELATIONSHIP]: <TeamOutlined />,
  [DecisionCategory.FINANCE]: <DollarOutlined />,
  [DecisionCategory.OTHER]: <QuestionCircleOutlined />,
};

const categoryColor: Record<DecisionCategory, string> = {
  [DecisionCategory.SHOPPING]: 'blue',
  [DecisionCategory.TIME]: 'orange',
  [DecisionCategory.CAREER]: 'purple',
  [DecisionCategory.RELATIONSHIP]: 'pink',
  [DecisionCategory.FINANCE]: 'green',
  [DecisionCategory.OTHER]: 'default',
};

const statusLabel: Record<CaseStatus, string> = {
  [CaseStatus.IN_PROGRESS]: '信息收集中',
  [CaseStatus.PENDING_DEBATE]: '待辩论',
  [CaseStatus.DEBATING]: '辩论中',
  [CaseStatus.VERDICTED]: '已判决',
  [CaseStatus.CLOSED]: '已关闭',
};

const statusColor: Record<CaseStatus, string> = {
  [CaseStatus.IN_PROGRESS]: 'processing',
  [CaseStatus.PENDING_DEBATE]: 'default',
  [CaseStatus.DEBATING]: 'warning',
  [CaseStatus.VERDICTED]: 'success',
  [CaseStatus.CLOSED]: 'default',
};

export default function HomePage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCaseList()
      .then((res) => {
        if (!cancelled) setCases(res.data);
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
        {cases.map((c) => (
          <Col xs={24} sm={12} key={c.id}>
            <Card
              hoverable
              onClick={() => {
                if (c.status === CaseStatus.VERDICTED || c.hasVerdict) {
                  navigate(`/verdict/${c.id}`);
                } else {
                  navigate(`/chat/${c.id}`);
                }
              }}
              style={{ borderRadius: 8 }}
            >
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <div>
                  <Tag icon={categoryIcon[c.category]} color={categoryColor[c.category]}>
                    {c.category}
                  </Tag>
                  <Tag color={statusColor[c.status]}>{statusLabel[c.status]}</Tag>
                </div>
                <Typography.Text strong style={{ fontSize: 16 }}>
                  {c.title}
                </Typography.Text>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {c.messageCount} 条消息 · {new Date(c.updatedAt).toLocaleDateString('zh-CN')}
                  </Typography.Text>
                  <RightOutlined style={{ color: '#ccc', fontSize: 12 }} />
                </div>
              </div>
            </Card>
          </Col>
        ))}
      </Row>
    </div>
  );
}
