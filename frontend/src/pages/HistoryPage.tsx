import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Tag, Typography, Empty, Spin, List, Space, Button } from 'antd';
import { ArrowLeftOutlined, RightOutlined, ShoppingCartOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { HistoryItem, HistoryResult, CaseType } from '../types';
import { getHistory } from '../api';

const resultMeta: Record<HistoryResult, { label: string; color: string; icon: string }> = {
  [HistoryResult.WORTH]: { label: '满意', color: 'green', icon: '👍' },
  [HistoryResult.REGRET]: { label: '后悔', color: 'red', icon: '👎' },
  [HistoryResult.NEUTRAL]: { label: '中立', color: 'default', icon: '🤔' },
};

const typeIcon: Record<CaseType, React.ReactNode> = {
  [CaseType.SHOPPING]: <ShoppingCartOutlined />,
  [CaseType.TIME]: <ClockCircleOutlined />,
};

export default function HistoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const load = (p: number) => {
    setLoading(true);
    getHistory({ page: p, page_size: 10 })
      .then((res) => { setItems(res.items); setTotal(res.total); setPage(res.page); })
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => { load(1); }, []);

  return (
    <div>
      <Space style={{ marginBottom: 24, cursor: 'pointer' }} onClick={() => navigate('/')}>
        <ArrowLeftOutlined />
        <Typography.Text type="secondary">返回首页</Typography.Text>
      </Space>
      <Typography.Title level={3} style={{ marginBottom: 24 }}>决策历史记录</Typography.Title>

      {loading ? (
        <div style={{ textAlign: 'center', paddingTop: 60 }}><Spin size="large" /></div>
      ) : items.length === 0 ? (
        <Empty description="暂无历史记录" />
      ) : (
        <>
          <List
            dataSource={items}
            renderItem={(item) => {
              const r = resultMeta[item.result] ?? { label: item.result, color: 'default', icon: '📝' };
              return (
                <Card
                  hoverable
                  style={{ borderRadius: 8, marginBottom: 12 }}
                  onClick={() => {
                    if (item.report_id) navigate(`/verdict/${item.case_id}`);
                    else navigate(`/chat/${item.case_id}`);
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                    <Space direction="vertical" size={4} style={{ flex: 1 }}>
                      <Space>
                        <Tag icon={typeIcon[item.case_type]}>{item.case_type}</Tag>
                        <Tag color={r.color}>{r.icon} {r.label}</Tag>
                      </Space>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>{item.summary}</Typography.Text>
                    </Space>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
                        {new Date(item.created_at).toLocaleDateString('zh-CN')}
                      </Typography.Text>
                      <RightOutlined style={{ color: '#ccc', marginTop: 4 }} />
                    </div>
                  </div>
                </Card>
              );
            }}
          />
          {total > 10 && (
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Button onClick={() => load(page + 1)} disabled={page * 10 >= total}>加载更多</Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
