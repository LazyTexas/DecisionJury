import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Input, Button, Typography, message, Space } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import { CaseType } from '../types';
import { createCase, appendLocalAssistantMessage, isMockMode } from '../api';

export default function CreateCasePage() {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (values: { title: string; description: string }) => {
    setSubmitting(true);
    try {
      // 当前 MVP 仅支持购物决策（后端辩论引擎只支持 shopping）。
      // 未来 time 上线后，重新开放 case_type 选择即可。
      const res = await createCase({
        case_type: CaseType.SHOPPING,
        title: values.title,
        description: values.description,
      });
      message.success('案件创建成功！');
      // 后端返回首个追问 next_question：作为对话首条助手引导持久化，
      // 进入 ChatPage 后用户一上来就知道该补充什么。
      // 仅真实模式需要（mock 模式自带欢迎语；本地缓存由服务端数据驱动）。
      if (res.case_id && res.next_question && !isMockMode) {
        appendLocalAssistantMessage(res.case_id, res.next_question);
      }
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
        >
          <Form.Item
            name="title"
            label="决策标题"
            rules={[{ required: true, message: '请输入决策标题' }]}
          >
            <Input placeholder="例：是否购买降噪耳机" maxLength={100} showCount />
          </Form.Item>

          <Form.Item name="description"
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
