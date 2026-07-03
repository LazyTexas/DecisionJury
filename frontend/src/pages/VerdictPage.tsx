import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Typography,
  Card,
  Tag,
  Spin,
  Button,
  Space,
  Divider,
  Progress,
  Empty,
  Descriptions,
  List,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MinusCircleOutlined,
  ThunderboltOutlined,
  SwapOutlined,
} from '@ant-design/icons';
import { Verdict, VerdictTendency, Case } from '../types';
import { getVerdict, getCaseDetail } from '../api';

const tendencyConfig: Record<VerdictTendency, { label: string; color: string; icon: React.ReactNode }> = {
  [VerdictTendency.SUPPORT]: { label: '支持', color: 'success', icon: <CheckCircleOutlined /> },
  [VerdictTendency.OPPOSE]: { label: '反对', color: 'error', icon: <CloseCircleOutlined /> },
  [VerdictTendency.NEUTRAL]: { label: '中立', color: 'default', icon: <MinusCircleOutlined /> },
};

export default function VerdictPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [caseData, setCaseData] = useState<Case | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;

    Promise.all([getVerdict(caseId), getCaseDetail(caseId)])
      .then(([v, c]) => {
        if (cancelled) return;
        setVerdict(v);
        setCaseData(c);
        if (!v) setError('判决书尚未生成');
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || '加载失败');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [caseId]);

  if (loading) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Spin size="large" />
        <p style={{ marginTop: 16, color: '#999' }}>加载判决书中…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Typography.Text type="danger">{error}</Typography.Text>
        <br />
        <Space style={{ marginTop: 16 }}>
          <Button onClick={() => navigate('/')}>返回首页</Button>
          <Button type="primary" onClick={() => navigate(`/chat/${caseId}`)}>
            回到对话
          </Button>
        </Space>
      </div>
    );
  }

  if (!verdict) {
    return (
      <Empty description="暂无判决书" style={{ paddingTop: 120 }}>
        <Space>
          <Button onClick={() => navigate('/')}>返回首页</Button>
          <Button type="primary" onClick={() => navigate(`/chat/${caseId}`)}>
            继续对话
          </Button>
        </Space>
      </Empty>
    );
  }

  const tendency = tendencyConfig[verdict.tendency];

  return (
    <div>
      <Space style={{ marginBottom: 24, cursor: 'pointer' }} onClick={() => navigate('/')}>
        <ArrowLeftOutlined />
        <Typography.Text type="secondary">返回首页</Typography.Text>
      </Space>

      {/* 判决书头部 */}
      <Card style={{ borderRadius: 8, marginBottom: 24 }}>
        <div style={{ textAlign: 'center' }}>
          <Tag
            icon={tendency.icon}
            color={tendency.color}
            style={{ padding: '4px 16px', fontSize: 16, borderRadius: 20, marginBottom: 16 }}
          >
            {tendency.label}
          </Tag>
          <Typography.Title level={3} style={{ marginBottom: 8 }}>
            {verdict.title || caseData?.title}
          </Typography.Title>
          <Typography.Paragraph
            style={{ fontSize: 16, color: '#555', maxWidth: 600, margin: '0 auto' }}
          >
            {verdict.conclusion}
          </Typography.Paragraph>

          {verdict.confidenceScore !== undefined && (
            <div style={{ maxWidth: 300, margin: '16px auto 0' }}>
              <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>
                置信度评分
              </Typography.Text>
              <Progress
                percent={verdict.confidenceScore}
                status={verdict.confidenceScore >= 80 ? 'success' : verdict.confidenceScore >= 60 ? 'active' : 'exception'}
                strokeColor={verdict.confidenceScore >= 80 ? '#52c41a' : verdict.confidenceScore >= 60 ? '#faad14' : '#ff4d4f'}
              />
            </div>
          )}
        </div>
      </Card>

      {/* 详细分析 */}
      <Card title="详细分析" style={{ borderRadius: 8, marginBottom: 24 }}>
        <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8 }}>
          {verdict.analysis}
        </Typography.Paragraph>
      </Card>

      {/* 正反论点对比 */}
      <Card title="正反方论点" style={{ borderRadius: 8, marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 250 }}>
            <div style={{ marginBottom: 12 }}>
              <ThunderboltOutlined style={{ color: '#faad14', marginRight: 8 }} />
              <Typography.Text strong>正方论点</Typography.Text>
            </div>
            <List
              dataSource={verdict.arguments.pro}
              renderItem={(item, i) => (
                <List.Item key={i} style={{ padding: '8px 0' }}>
                  <Typography.Text>✅ {item}</Typography.Text>
                </List.Item>
              )}
            />
          </div>
          <Divider type="vertical" style={{ height: 'auto' }} />
          <div style={{ flex: 1, minWidth: 250 }}>
            <div style={{ marginBottom: 12 }}>
              <SwapOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
              <Typography.Text strong>反方论点</Typography.Text>
            </div>
            <List
              dataSource={verdict.arguments.con}
              renderItem={(item, i) => (
                <List.Item key={i} style={{ padding: '8px 0' }}>
                  <Typography.Text>❌ {item}</Typography.Text>
                </List.Item>
              )}
            />
          </div>
        </div>
      </Card>

      {/* 判决理由 */}
      {verdict.reasons.length > 0 && (
        <Card title="判决理由" style={{ borderRadius: 8, marginBottom: 24 }}>
          <List
            dataSource={verdict.reasons}
            renderItem={(item, i) => (
              <List.Item key={i} style={{ padding: '8px 0' }}>
                <Typography.Text>
                  <strong>{i + 1}.</strong> {item}
                </Typography.Text>
              </List.Item>
            )}
          />
        </Card>
      )}

      {/* 建议 */}
      <Card title="给用户的建议" style={{ borderRadius: 8, marginBottom: 24 }}>
        <Typography.Paragraph style={{ whiteSpace: 'pre-wrap', lineHeight: 1.8, fontSize: 15 }}>
          {verdict.suggestion}
        </Typography.Paragraph>
      </Card>

      {/* 元信息 */}
      <Card style={{ borderRadius: 8 }}>
        <Descriptions size="small" column={{ xs: 1, sm: 2 }}>
          <Descriptions.Item label="判决书 ID">{verdict.id}</Descriptions.Item>
          <Descriptions.Item label="生成时间">
            {new Date(verdict.createdAt).toLocaleString('zh-CN')}
          </Descriptions.Item>
          {verdict.relatedCases && verdict.relatedCases.length > 0 && (
            <Descriptions.Item label="参考案例">
              {verdict.relatedCases.join('、')}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>
    </div>
  );
}
