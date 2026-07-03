import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Card,
  Form,
  Input,
  Select,
  Button,
  Typography,
  message,
  Space,
} from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { DecisionCategory, CreateCaseFormData } from '../types';
import { createCase } from '../api';

const { TextArea } = Input;

export default function CreateCasePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm<CreateCaseFormData>();
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (values: CreateCaseFormData) => {
    setSubmitting(true);
    try {
      const res = await createCase({
        title: values.title,
        category: values.category,
        description: values.context || values.title,
      });
      message.success('案件创建成功！');
      navigate(`/chat/${res.case.id}`);
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
          initialValues={{ category: DecisionCategory.OTHER }}
        >
          <Form.Item
            name="title"
            label="决策标题"
            rules={[{ required: true, message: '请输入决策标题' }]}
          >
            <Input placeholder="例：要不要买这台 MacBook Pro M4？" maxLength={100} showCount />
          </Form.Item>

          <Form.Item
            name="category"
            label="决策类别"
            rules={[{ required: true, message: '请选择决策类别' }]}
          >
            <Select>
              <Select.Option value={DecisionCategory.SHOPPING}>🛒 购物决策</Select.Option>
              <Select.Option value={DecisionCategory.TIME}>⏰ 时间/日程决策</Select.Option>
              <Select.Option value={DecisionCategory.CAREER}>💼 职业决策</Select.Option>
              <Select.Option value={DecisionCategory.RELATIONSHIP}>🤝 关系决策</Select.Option>
              <Select.Option value={DecisionCategory.FINANCE}>💰 财务决策</Select.Option>
              <Select.Option value={DecisionCategory.OTHER}>❓ 其他</Select.Option>
            </Select>
          </Form.Item>

          <Form.Item
            name="context"
            label="详细描述"
            rules={[{ required: true, message: '请描述你的决策背景' }]}
          >
            <TextArea
              rows={5}
              placeholder="说说你在纠结什么？有哪些选择？你的顾虑是什么？&#10;例：我现在用的是 2019 年的 Intel MacBook Pro，最近感觉有点卡了。看到新出的 M4 性能提升很大，但价格要 2 万多，有点犹豫。"
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
