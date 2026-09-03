import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Tag, Typography, Empty, Spin, Row, Col, Space, Button, Divider, List } from 'antd';
import {
  ShoppingCartOutlined,
  ClockCircleOutlined,
  RightOutlined,
  HistoryOutlined,
} from '@ant-design/icons';
import { CaseSummary, CaseType, CaseStatus, HistoryItem, HistoryResult } from '../types';
import { getCaseList, getHistory } from '../api';
import { CASE_STATUS_META, CASE_TYPE_META, HISTORY_RESULT_META } from '../constants';
import { formatDate } from '../utils/format';

const caseTypeIcon: Record<CaseType, React.ReactNode> = {
  [CaseType.SHOPPING]: <ShoppingCartOutlined />,
  [CaseType.TIME]: <ClockCircleOutlined />,
};

export default function HomePage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getCaseList(), getHistory({ page: 1, page_size: 5 })])
      .then(([c, h]) => {
        if (!cancelled) {
          setCases(c.items);
          setHistoryItems(h.items);
        }
      })
      .catch((err) => { if (!cancelled) setError(err.message || '加载失败'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  if (loading) {
    return <div style={{ textAlign: 'center', paddingTop: 120 }}><Spin size="large" /><p style={{ marginTop: 16, color: '#999' }}>加载中…</p></div>;
  }

  if (error) {
    return <div style={{ textAlign: 'center', paddingTop: 120 }}><Typography.Text type="danger">{error}</Typography.Text></div>;
  }

  return (
    <div>
      {/* 案件列表 */}
      <Typography.Title level={3} style={{ marginBottom: 24 }}>我的决策案件</Typography.Title>
      {cases.length === 0 ? (
        <Empty style={{ marginBottom: 32 }} description="还没有任何决策案件">
          <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
            点击右上角「新建决策」开始你的第一个冷静决策
          </Typography.Text>
        </Empty>
      ) : (
        <Row gutter={[16, 16]} style={{ marginBottom: 32 }}>
          {cases.map((c) => {
            const cat = CASE_TYPE_META[c.case_type];
            const st = CASE_STATUS_META[c.status];
            return (
              <Col xs={24} sm={12} key={c.case_id}>
                <Card hoverable onClick={() => {
                  if (c.status === CaseStatus.COMPLETED || c.has_report) navigate(`/verdict/${c.case_id}`);
                  else navigate(`/chat/${c.case_id}`);
                }} style={{ borderRadius: 8 }}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                    <div>
                      <Tag icon={caseTypeIcon[c.case_type]} color={cat.color}>{cat.label}</Tag>
                      <Tag color={st.color}>{st.label}</Tag>
                    </div>
                    <Typography.Text strong style={{ fontSize: 16 }}>{c.title}</Typography.Text>
                    <Typography.Paragraph type="secondary" ellipsis={{ rows: 2 }} style={{ margin: 0, fontSize: 13 }}>
                      {c.description}
                    </Typography.Paragraph>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {c.message_count} 条消息 · {formatDate(c.updated_at)}
                      </Typography.Text>
                      <RightOutlined style={{ color: '#ccc', fontSize: 12 }} />
                    </div>
                  </div>
                </Card>
              </Col>
            );
          })}
        </Row>
      )}

      {/* 历史记录区域 */}
      <Divider />
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={4} style={{ margin: 0 }}>
          <HistoryOutlined style={{ marginRight: 8 }} />决策历史记录
        </Typography.Title>
        <Button type="link" onClick={() => navigate('/history')}>查看全部 <RightOutlined /></Button>
      </div>

      {historyItems.length === 0 ? (
        <Typography.Text type="secondary">暂无历史记录</Typography.Text>
      ) : (
        <List
          dataSource={historyItems}
          renderItem={(item) => {
            const r = HISTORY_RESULT_META[item.result as HistoryResult] ?? { label: item.result, color: 'default', icon: '📝' };
            return (
              <List.Item
                style={{ cursor: 'pointer', padding: '12px 8px', borderRadius: 6 }}
                onClick={() => {
                  if (item.report_id) navigate(`/verdict/${item.case_id}`);
                  else if (item.case_id) navigate(`/chat/${item.case_id}`);
                }}
              >
                <Space direction="vertical" size={2} style={{ flex: 1 }}>
                  <Space>
                    <Tag color={r.color}>{r.icon} {r.label}</Tag>
                    <Typography.Text strong style={{ fontSize: 14 }}>{item.title}</Typography.Text>
                  </Space>
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {item.summary} · {formatDate(item.created_at)}
                  </Typography.Text>
                </Space>
                <RightOutlined style={{ color: '#ccc' }} />
              </List.Item>
            );
          }}
        />
      )}
    </div>
  );
}
