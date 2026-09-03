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
  Collapse,
  Timeline,
  Result,
} from 'antd';
import {
  ArrowLeftOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  MinusCircleOutlined,
  ThunderboltOutlined,
  SwapOutlined,
  ToolOutlined,
  HistoryOutlined,
  RobotOutlined,
} from '@ant-design/icons';
import { DecisionReport, RagEvidence, ToolResult, TraceItem } from '../types';
import { getReport, getTrace } from '../api';
import { DECISION_META, CASE_TYPE_META, TRACE_NAME_LABEL, TRACE_TYPE_LABEL } from '../constants';
import { formatDateTime } from '../utils/format';
import FeedbackModal from '../components/FeedbackModal';

const decisionIcon: Record<string, React.ReactNode> = {
  buy: <CheckCircleOutlined />,
  accept: <CheckCircleOutlined />,
  partial_accept: <CheckCircleOutlined />,
  delay: <MinusCircleOutlined />,
  reject: <CloseCircleOutlined />,
  alternative: <SwapOutlined />,
};

const traceTypeColor: Record<string, string> = {
  agent: 'blue',
  rag_search: 'purple',
  tool_call: 'orange',
};

export default function VerdictPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [report, setReport] = useState<DecisionReport | null>(null);
  const [steps, setSteps] = useState<TraceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  useEffect(() => {
    if (!caseId) return;
    let cancelled = false;

    Promise.all([
      getReport(caseId),
      getTrace(caseId).catch(() => ({ case_id: caseId!, trace: [] })),
    ])
      .then(([r, t]) => {
        if (cancelled) return;
        setReport(r);
        setSteps(t.trace);
        if (!r) setError('判决书尚未生成');
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

  if (error || !report) {
    return (
      <Result
        status="info"
        title="暂无判决书"
        subTitle={error || '该案件尚未生成判决书，可能还在信息收集中。'}
        style={{ paddingTop: 60 }}
        extra={
          <Space>
            <Button onClick={() => navigate('/')}>返回首页</Button>
            <Button type="primary" onClick={() => navigate(`/chat/${caseId}`)}>回到对话</Button>
          </Space>
        }
      />
    );
  }

  const meta = DECISION_META[report.final_decision] ?? {
    label: report.final_decision,
    color: 'default',
  };

  return (
    <div>
      <Space style={{ marginBottom: 24, cursor: 'pointer' }} onClick={() => navigate('/')}>
        <ArrowLeftOutlined />
        <Typography.Text type="secondary">返回首页</Typography.Text>
      </Space>

      {/* 头部：裁决徽标 */}
      <Card style={{ borderRadius: 8, marginBottom: 24 }}>
        <div style={{ textAlign: 'center' }}>
          <Tag
            icon={decisionIcon[report.final_decision]}
            color={meta.color}
            style={{ padding: '4px 16px', fontSize: 16, borderRadius: 20, marginBottom: 16 }}
          >
            {meta.label}
          </Tag>
          <Typography.Title level={3} style={{ marginBottom: 8 }}>
            {report.case_summary}
          </Typography.Title>
          <Typography.Paragraph style={{ fontSize: 16, color: '#555', maxWidth: 600, margin: '0 auto' }}>
            {report.summary}
          </Typography.Paragraph>
          <div style={{ maxWidth: 300, margin: '16px auto 0' }}>
            <Typography.Text type="secondary" style={{ display: 'block', marginBottom: 4 }}>
              置信度
            </Typography.Text>
            <Progress
              percent={Math.round(report.confidence * 100)}
              status={report.confidence >= 0.8 ? 'success' : report.confidence >= 0.6 ? 'active' : 'exception'}
            />
          </div>
        </div>
      </Card>

      {/* 正反方观点 */}
      <Card title="正反方观点" style={{ borderRadius: 8, marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 24, flexWrap: 'wrap' }}>
          <div style={{ flex: 1, minWidth: 250 }}>
            <div style={{ marginBottom: 12 }}>
              <ThunderboltOutlined style={{ color: '#faad14', marginRight: 8 }} />
              <Typography.Text strong>正方观点</Typography.Text>
            </div>
            <List
              dataSource={report.pro_points}
              renderItem={(item) => (
                <List.Item style={{ padding: '8px 0' }}>
                  <Typography.Text>✅ {item}</Typography.Text>
                </List.Item>
              )}
            />
          </div>
          <Divider type="vertical" style={{ height: 'auto' }} />
          <div style={{ flex: 1, minWidth: 250 }}>
            <div style={{ marginBottom: 12 }}>
              <SwapOutlined style={{ color: '#ff4d4f', marginRight: 8 }} />
              <Typography.Text strong>反方观点</Typography.Text>
            </div>
            <List
              dataSource={report.con_points}
              renderItem={(item) => (
                <List.Item style={{ padding: '8px 0' }}>
                  <Typography.Text>❌ {item}</Typography.Text>
                </List.Item>
              )}
            />
          </div>
        </div>
      </Card>

      {/* 后续动作 */}
      {report.next_actions.length > 0 && (
        <Card title="后续建议" style={{ borderRadius: 8, marginBottom: 24 }}>
          <List
            dataSource={report.next_actions}
            renderItem={(item) => (
              <List.Item style={{ padding: '8px 0' }}>
                <Typography.Text>👉 {item}</Typography.Text>
              </List.Item>
            )}
          />
        </Card>
      )}

      {/* 证据与工具（折叠） */}
      <Collapse
        style={{ marginBottom: 24, borderRadius: 8 }}
        items={[
          {
            key: 'rag',
            label: (
              <span><HistoryOutlined style={{ marginRight: 8 }} />RAG 证据 ({report.rag_evidence.length})</span>
            ),
            children: report.rag_evidence.length === 0
              ? <Typography.Text type="secondary">无引用证据</Typography.Text>
              : report.rag_evidence.map((ev: RagEvidence) => (
                  <Card key={ev.id} size="small" style={{ marginBottom: 8 }}>
                    <Typography.Text strong>{ev.title}</Typography.Text>
                    <Typography.Paragraph type="secondary" style={{ margin: '4px 0' }}>
                      {ev.content}
                    </Typography.Paragraph>
                    <Tag>相关性: {ev.score}</Tag>
                    <Tag color="blue">{ev.source}</Tag>
                  </Card>
                )),
          },
          {
            key: 'tools',
            label: (
              <span><ToolOutlined style={{ marginRight: 8 }} />工具调用结果 ({report.tool_results.length})</span>
            ),
            children: report.tool_results.length === 0
              ? <Typography.Text type="secondary">无工具调用</Typography.Text>
              : report.tool_results.map((tr: ToolResult, i: number) => (
                  <Card key={i} size="small" style={{ marginBottom: 8 }}>
                    <Typography.Text strong>{tr.tool_name}</Typography.Text>
                    <Tag color={tr.status === 'success' ? 'success' : 'error'} style={{ marginLeft: 8 }}>
                      {tr.status}
                    </Tag>
                    <Typography.Paragraph type="secondary" style={{ margin: '4px 0' }}>
                      {tr.summary}
                    </Typography.Paragraph>
                    {tr.risk_level && <Tag color="orange">风险: {tr.risk_level}</Tag>}
                  </Card>
                )),
          },
        ]}
      />

      {/* Agent 执行轨迹：有序时间线 */}
      {steps.length > 0 && (
        <Card
          style={{ borderRadius: 8, marginBottom: 24 }}
          title={
            <Space>
              <RobotOutlined />
              Agent 执行轨迹
            </Space>
          }
        >
          <Timeline
            items={steps.map((item) => {
              const ok = item.status === 'completed';
              return {
                color: ok ? 'green' : 'red',
                children: (
                  <div style={{ paddingBottom: 8 }}>
                    <Space wrap size={8}>
                      <Tag color={traceTypeColor[item.type] ?? 'default'}>
                        {TRACE_TYPE_LABEL[item.type] ?? item.type}
                      </Tag>
                      <Typography.Text strong>
                        {TRACE_NAME_LABEL[item.name] ?? item.name}
                      </Typography.Text>
                      <Tag color={ok ? 'success' : 'error'}>
                        {ok ? '完成' : '失败'}
                      </Tag>
                      {typeof item.duration_ms === 'number' && (
                        <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                          {item.duration_ms}ms
                        </Typography.Text>
                      )}
                    </Space>
                    <div style={{ marginTop: 4 }}>
                      <Typography.Text type="secondary" style={{ fontSize: 13 }}>
                        {item.input_summary} → {item.output_summary}
                      </Typography.Text>
                    </div>
                    {item.error && (
                      <Typography.Text type="danger" style={{ fontSize: 12 }}>
                        {item.error}
                      </Typography.Text>
                    )}
                  </div>
                ),
              };
            })}
          />
        </Card>
      )}

      {/* 元信息 */}
      <Card style={{ borderRadius: 8, marginBottom: 24 }}>
        <Descriptions size="small" column={{ xs: 1, sm: 2 }}>
          <Descriptions.Item label="判决书 ID">{report.report_id}</Descriptions.Item>
          <Descriptions.Item label="生成时间">{formatDateTime(report.created_at)}</Descriptions.Item>
          <Descriptions.Item label="案件类型">
            {CASE_TYPE_META[report.case_type as keyof typeof CASE_TYPE_META]?.label ?? report.case_type}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* 复盘按钮 */}
      <div style={{ textAlign: 'center', marginBottom: 24 }}>
        <Button type="default" size="large" onClick={() => setFeedbackOpen(true)}>
          提交决策复盘
        </Button>
        <Typography.Text type="secondary" style={{ display: 'block', marginTop: 4, fontSize: 12 }}>
          你的反馈将帮助未来的决策更准确
        </Typography.Text>
      </div>

      {/* 复盘 Modal */}
      <FeedbackModal caseId={caseId!} open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </div>
  );
}
