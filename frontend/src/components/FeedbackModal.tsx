import { useState } from 'react';
import { Modal, Form, Select, Rate, Input, Button, message } from 'antd';
import { submitFeedback } from '../api';

interface FeedbackModalProps {
  caseId: string;
  open: boolean;
  onClose: () => void;
}

export default function FeedbackModal({ caseId, open, onClose }: FeedbackModalProps) {
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (values: { actual_action: string; satisfaction: number; review?: string }) => {
    setSubmitting(true);
    try {
      const res = await submitFeedback(caseId, values);
      message.success('复盘已保存');
      onClose();
    } catch (err: any) {
      message.error(err.message || '提交失败');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Modal
      title="决策复盘"
      open={open}
      onCancel={onClose}
      footer={null}
      destroyOnClose
    >
      <Form form={form} layout="vertical" onFinish={handleSubmit} requiredMark={false}>
        <Form.Item name="actual_action" label="你最终做了什么？" rules={[{ required: true, message: '请选择' }]}>
          <Select placeholder="请选择">
            <Select.Option value="bought">买了/做了</Select.Option>
            <Select.Option value="not_bought">没买/没做</Select.Option>
            <Select.Option value="delayed">延后了</Select.Option>
            <Select.Option value="other">其他</Select.Option>
          </Select>
        </Form.Item>

        <Form.Item name="satisfaction" label="满意度评分" rules={[{ required: true, message: '请评分' }]}>
          <Rate />
        </Form.Item>

        <Form.Item name="review" label="复盘感想（选填）">
          <Input.TextArea rows={3} placeholder="分享一下你的感受…" />
        </Form.Item>

        <Form.Item>
          <Button type="primary" htmlType="submit" loading={submitting} block>
            提交复盘
          </Button>
        </Form.Item>
      </Form>
    </Modal>
  );
}
