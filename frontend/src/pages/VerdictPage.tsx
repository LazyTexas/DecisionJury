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
} from '@ant-design/icons';
import { DecisionReport, RagEvidence, ToolResult, TraceItem } from '../types';
import { getReport, getTrace } from '../api';

const finalDecisionMeta: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  buy: { label: '建议购买', color: 'success', icon: <CheckCircleOutlined /> },
  accept: { label: '建议接受', color: 'success', icon: <CheckCircleOutlined /> },
  partial_accept: { label: '建议部分接受', color: 'processing', icon: <CheckCircleOutlined /> },
  delay: { label: '建议暂缓', color: 'warning', icon: <MinusCircleOutlined /> },
  reject: { label: '建议不购买/拒绝', color: 'error', icon: <CloseCircleOutlined /> },
  alternative: { label: '建议寻找替代方案', color: 'default', icon: <SwapOutlined /> },
};

export default function VerdictPage() {
  const { caseId } = useParams<{ caseId: string }>();
  const navigate = useNavigate();

  const [report, setReport] = useState<DecisionReport | null>(null);
  const [steps, setSteps] = useState<TraceItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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

  if (error) {
    return (
      <div style={{ textAlign: 'center', paddingTop: 120 }}>
        <Typography.Text type="danger">{error}</Typography.Text>
        <br />
        <Space style={{ marginTop: 16 }}>
          <Button onClick={() => navigate('/')}>返回首页</Button>
          <Button type="primary" onClick={() => navigate(`/chat/${caseId}`)}>回到对话</Button>
        </Space>
      </div>
    );
  }

  if (!report) {
    return (
      <Empty description="暂无判决书" style={{ paddingTop: 120 }}>
        <Button onClick={() => navigate('/')}>返回首页</Button>
      </Empty>
    );
  }

  const decision = finalDecisionMeta[report.final_decision] ?? { label: report.final_decision, color: 'default', icon: null };

  return (
    <div>
      <Space style={{ marginBottom: 24, cursor: 'pointer' }} onClick={() => navigate('/')}>
        <ArrowLeftOutlined />
        <Typography.Text type="secondary">返回首页</Typography.Text>
      </Space>

      {/* 头部 */}
      <Card style={{ borderRadius: 8, marginBottom: 24 }}>
        <div style={{ textAlign: 'center' }}>
          <Tag
            icon={decision.icon}
            color={decision.color}
            style={{ padding: '4px 16px', fontSize: 16, borderRadius: 20, marginBottom: 16 }}
          >
            {decision.label}
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

      {/* RAG 证据和工具结果（折叠） */}
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

      {/* Agent 执行轨迹 */}
      {steps.length > 0 && (
        <Collapse
          style={{ marginBottom: 24, borderRadius: 8 }}
          items={[{
            key: 'trace',
            label: <span>Agent 执行轨迹</span>,
            children: (
              <List
                dataSource={steps}
                renderItem={(item: any) => (
                  <List.Item style={{ padding: '8px 0' }}>
                    <Space>
                      <Tag color={item.status === 'completed' ? 'success' : 'error'}>
                        {item.type}: {item.name}
                      </Tag>
                      <Typography.Text type="secondary">{item.duration_ms}ms</Typography.Text>
                    </Space>
                    <div>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {item.input_summary} → {item.output_summary}
                      </Typography.Text>
                    </div>
                  </List.Item>
                )}
              />
            ),
          }]}
        />
      )}

      {/* 元信息 */}
      <Card style={{ borderRadius: 8 }}>
        <Descriptions size="small" column={{ xs: 1, sm: 2 }}>
          <Descriptions.Item label="判决书 ID">{report.report_id}</Descriptions.Item>
          <Descriptions.Item label="生成时间">
            {new Date(report.created_at).toLocaleString('zh-CN')}
          </Descriptions.Item>
          <Descriptions.Item label="案件类型">{report.case_type}</Descriptions.Item>
        </Descriptions>
      </Card>
    </div>
  );
}
