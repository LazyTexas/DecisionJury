import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card, Tag, Typography, Empty, Spin, Row, Col, Space, Button, Divider, List,
  Collapse, Popconfirm, message,
} from 'antd';
import {
  ShoppingCartOutlined,
  ClockCircleOutlined,
  RightOutlined,
  HistoryOutlined,
  DeleteOutlined,
  PlusOutlined,
} from '@ant-design/icons';
import { CaseSummary, CaseType, CaseStatus, HistoryItem, HistoryResult } from '../types';
import { getCaseList, getHistory, deleteCase, clearLocalMessages } from '../api';
import { CASE_STATUS_META, CASE_TYPE_META, HISTORY_RESULT_META } from '../constants';
import { formatDate } from '../utils/format';

const caseTypeIcon: Record<CaseType, React.ReactNode> = {
  [CaseType.SHOPPING]: <ShoppingCartOutlined />,
  [CaseType.TIME]: <ClockCircleOutlined />,
};

/** 案件分组配置（进行中 → 已完成 → 已拒绝 → 已归档） */
interface CaseGroup {
  key: string;
  label: string;
  color: string;
  statuses: CaseStatus[];
}

const CASE_GROUPS: CaseGroup[] = [
  {
    key: 'active',
    label: '进行中',
    color: 'processing',
    statuses: [CaseStatus.COLLECTING, CaseStatus.READY_FOR_DEBATE, CaseStatus.DEBATING],
  },
  { key: 'completed', label: '已完成', color: 'success', statuses: [CaseStatus.COMPLETED] },
  { key: 'rejected', label: '已拒绝', color: 'error', statuses: [CaseStatus.REJECTED] },
  { key: 'archived', label: '已归档', color: 'default', statuses: [CaseStatus.ARCHIVED] },
];

export default function HomePage() {
  const navigate = useNavigate();
  const [cases, setCases] = useState<CaseSummary[]>([]);
  const [historyItems, setHistoryItems] = useState<HistoryItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadData = useCallback(() => {
    setLoading(true);
    Promise.all([getCaseList(), getHistory({ page: 1, page_size: 5 })])
      .then(([c, h]) => {
        setCases(c.items);
        setHistoryItems(h.items);
      })
      .catch((err) => { setError(err.message || '加载失败'); })
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleDelete = async (c: CaseSummary) => {
    setDeletingId(c.case_id);
    try {
      await deleteCase(c.case_id);
      // 同步清理本地会话缓存，避免残留数据
      clearLocalMessages(c.case_id);
      message.success(`已删除「${c.title}」`);
      setCases((prev) => prev.filter((x) => x.case_id !== c.case_id));
    } catch (err: any) {
      message.error(err.message || '删除失败，请稍后重试');
    } finally {
      setDeletingId(null);
    }
  };

  const openCase = (c: CaseSummary) => {
    if (c.status === CaseStatus.COMPLETED || c.has_report) navigate(`/verdict/${c.case_id}`);
    else navigate(`/chat/${c.case_id}`);
  };

  if (loading) {
    return <div style={{ textAlign: 'center', paddingTop: 120 }}><Spin size="large" /><p style={{ marginTop: 16, color: '#999' }}>加载中…</p></div>;
  }

  if (error && cases.length === 0) {
    return <div style={{ textAlign: 'center', paddingTop: 120 }}><Typography.Text type="danger">{error}</Typography.Text></div>;
  }

  const groupItems = CASE_GROUPS
    .map((g) => ({ group: g, items: cases.filter((c) => g.statuses.includes(c.status)) }))
    .filter((x) => x.items.length > 0);

  return (
    <div>
      {/* 案件列表标题 + 操作 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Typography.Title level={3} style={{ margin: 0 }}>
          我的决策案件{cases.length > 0 && <Typography.Text type="secondary" style={{ fontSize: 14, fontWeight: 400, marginLeft: 8 }}>共 {cases.length} 个</Typography.Text>}
        </Typography.Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/create')}>
          新建决策
        </Button>
      </div>

      {cases.length === 0 ? (
        <Empty style={{ marginBottom: 32, paddingTop: 40 }} description="还没有任何决策案件">
          <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 16 }}>
            点击「新建决策」开始你的第一个冷静决策
          </Typography.Text>
          <Button type="primary" onClick={() => navigate('/create')}>新建决策</Button>
        </Empty>
      ) : (
        <Collapse
          style={{ marginBottom: 24, borderRadius: 8 }}
          defaultActiveKey={['active']}
          items={groupItems.map(({ group, items }) => ({
            key: group.key,
            label: (
              <Space size={8}>
                <Tag color={group.color} style={{ marginInlineEnd: 0 }}>{group.label}</Tag>
                <Typography.Text type="secondary" style={{ fontSize: 13 }}>{items.length} 个</Typography.Text>
              </Space>
            ),
            children: (
              <Row gutter={[16, 16]}>
                {items.map((c) => {
                  const cat = CASE_TYPE_META[c.case_type];
                  const st = CASE_STATUS_META[c.status];
                  return (
                    <Col xs={24} sm={12} key={c.case_id}>
                      <Card
                        hoverable
                        onClick={() => openCase(c)}
                        style={{ borderRadius: 8 }}
                      >
                        <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8 }}>
                            <Space size={4} wrap>
                              <Tag icon={caseTypeIcon[c.case_type]} color={cat.color} style={{ marginInlineEnd: 0 }}>{cat.label}</Tag>
                              <Tag color={st.color} style={{ marginInlineEnd: 0 }}>{st.label}</Tag>
                            </Space>
                            <Popconfirm
                              title="删除这个决策案件？"
                              description={`「${c.title}」及其全部对话记录将被删除，无法恢复。`}
                              okText="删除"
                              okButtonProps={{ danger: true }}
                              cancelText="取消"
                              onConfirm={(e) => { e?.stopPropagation(); handleDelete(c); }}
                              onCancel={(e) => e?.stopPropagation()}
                            >
                              <Button
                                type="text"
                                size="small"
                                danger
                                icon={<DeleteOutlined />}
                                loading={deletingId === c.case_id}
                                onClick={(e) => e.stopPropagation()}
                                style={{ flexShrink: 0 }}
                              />
                            </Popconfirm>
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
            ),
          }))}
        />
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
                  if (item.report_id && item.case_id) navigate(`/verdict/${item.case_id}`);
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
