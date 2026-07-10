import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Input, Select, Button, Typography, message, Space } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { CaseType } from '../types';
import { createCase } from '../api';

export default function CreateCasePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (values: { title: string; case_type: CaseType; description: string }) => {
    setSubmitting(true);
    try {
      const res = await createCase({
        case_type: values.case_type,
        title: values.title,
        description: values.description,
      });
      message.success('案件创建成功！');
      navigate(`/chat/${res.case_id}`);
    } catch (err: any) {
      message.error(err.message || '创建失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div style={{ maxWidth: 600, margin: '0 auto' }}>
      <Space style={{ marginBottom: 24, cursor: 'pointer' }} onClick={() => navigate('/')}>
        <ArrowLeftOutlined />
        <Typography.Text type="secondary">返回首页</Typography.Text>
      </Space>

      <Typography.Title level={3}>新建决策案件</Typography.Title>
      <Typography.Paragraph type="secondary" style={{ marginBottom: 32 }}>
        描述你正在纠结的决策，我会通过多轮对话帮你理清思路，最终生成一份「决策判决书」。
      </Typography.Paragraph>

      <Card style={{ borderRadius: 8 }}>
        <Form
          form={form}
          layout="vertical"
          onFinish={handleSubmit}
          requiredMark={false}
          initialValues={{ case_type: CaseType.SHOPPING }}
        >
          <Form.Item
            name="title"
            label="决策标题"
            rules={[{ required: true, message: '请输入决策标题' }]}
          >
            <Input placeholder="例：是否购买降噪耳机" maxLength={100} showCount />
          </Form.Item>

          <Form.Item
            name="case_type"
            label="决策类别"
            rules={[{ required: true, message: '请选择决策类别' }]}
          >
            <Select>
              <Select.Option value={CaseType.SHOPPING}>🛒 购物决策</Select.Option>
              <Select.Option value={CaseType.TIME}>⏰ 时间/日程决策</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="description"
            label="详细描述"
            rules={[{ required: true, message: '请描述你的决策背景' }]}
          >
            <Input.TextArea
              rows={5}
              placeholder="说说你在纠结什么？有哪些选择？你的顾虑是什么？"
              maxLength={1000}
              showCount
            />
          </Form.Item>

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={submitting} block size="large">
              提交决策
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
}
