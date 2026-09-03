import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Tag, Typography, Empty, Spin, List, Space, Button } from 'antd';
import { ArrowLeftOutlined, RightOutlined, ShoppingCartOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { HistoryItem, HistoryResult, CaseType } from '../types';
import { getHistory } from '../api';
import { HISTORY_RESULT_META, CASE_TYPE_META } from '../constants';
import { formatDate } from '../utils/format';

const typeIcon: Record<CaseType, React.ReactNode> = {
  [CaseType.SHOPPING]: <ShoppingCartOutlined />,
  [CaseType.TIME]: <ClockCircleOutlined />,
};

const PAGE_SIZE = 10;

export default function HistoryPage() {
  const navigate = useNavigate();
  const [items, setItems] = useState<HistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // 首屏加载
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    getHistory({ page: 1, page_size: PAGE_SIZE })
      .then((res) => { if (!cancelled) { setItems(res.items); setTotal(res.total); setPage(res.page); } })
      .catch((err) => { if (!cancelled) setError(err.message || '加载失败'); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, []);

  // 加载更多：追加下一页，而非替换
  const loadMore = async () => {
    if (loadingMore || items.length >= total) return;
    setLoadingMore(true);
    try {
      const res = await getHistory({ page: page + 1, page_size: PAGE_SIZE });
      setItems((prev) => [...prev, ...res.items]);
      setTotal(res.total);
      setPage(res.page);
    } catch (err: any) {
      setError(err.message || '加载失败');
    } finally {
      setLoadingMore(false);
    }
  };

  if (error && items.length === 0) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Typography.Text type="danger">{error}</Typography.Text>
      </div>
    );
  }

  const hasMore = items.length < total;

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
          {error && <Typography.Text type="danger" style={{ display: 'block', marginBottom: 12 }}>{error}</Typography.Text>}
          <List
            dataSource={items}
            renderItem={(item) => {
              const r = HISTORY_RESULT_META[item.result as HistoryResult] ?? { label: item.result, color: 'default', icon: '📝' };
              const cat = CASE_TYPE_META[item.case_type];
              return (
                <Card
                  hoverable
                  style={{ borderRadius: 8, marginBottom: 12 }}
                  onClick={() => {
                    if (item.report_id) navigate(`/verdict/${item.case_id}`);
                    else if (item.case_id) navigate(`/chat/${item.case_id}`);
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
                    <Space direction="vertical" size={4} style={{ flex: 1 }}>
                      <Space>
                        <Tag icon={typeIcon[item.case_type]} color={cat.color}>{cat.label}</Tag>
                        <Tag color={r.color}>{r.icon} {r.label}</Tag>
                      </Space>
                      <Typography.Text strong>{item.title}</Typography.Text>
                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>{item.summary}</Typography.Text>
                    </Space>
                    <div style={{ textAlign: 'right', flexShrink: 0 }}>
                      <Typography.Text type="secondary" style={{ fontSize: 12, display: 'block' }}>
                        {formatDate(item.created_at)}
                      </Typography.Text>
                      <RightOutlined style={{ color: '#ccc', marginTop: 4 }} />
                    </div>
                  </div>
                </Card>
              );
            }}
          />
          {hasMore && (
            <div style={{ textAlign: 'center', marginTop: 16 }}>
              <Button onClick={loadMore} loading={loadingMore}>
                加载更多
              </Button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
