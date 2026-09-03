// ============================================================
// 注册页
// 调用 POST /api/auth/register，成功后自动登录（后端返回用户身份）
// 并进入首页。
// ============================================================

import { useState } from 'react';
import { Link, Navigate, useNavigate } from 'react-router-dom';
import { Form, Input, Button, message, Typography } from 'antd';
import { UserOutlined, LockOutlined, SmileOutlined } from '@ant-design/icons';
import { useAuth } from '../auth/AuthContext';
import AuthShell from '../auth/AuthShell';

interface RegisterValues {
  user_id: string;
  name?: string;
  password: string;
  confirm: string;
}

export default function RegisterPage() {
  const { user, register } = useAuth();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  // 已登录访问注册页 → 直接回首页
  if (user) {
    return <Navigate to="/" replace />;
  }

  const handleFinish = async (values: RegisterValues) => {
    setSubmitting(true);
    try {
      await register(
        values.user_id.trim(),
        values.name?.trim() || values.user_id.trim(),
        values.password,
      );
      message.success('注册成功，已自动登录');
      navigate('/', { replace: true });
    } catch (err: any) {
      message.error(err.message || '注册失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="注册" subtitle="选择一个用户 ID，注册后即刻开始冷静决策">
      <Form
        layout="vertical"
        onFinish={handleFinish}
        requiredMark={false}
        size="large"
        initialValues={{ user_id: '', name: '' }}
      >
        <Form.Item
          name="user_id"
          label="用户 ID"
          rules={[
            { required: true, message: '请输入用户 ID' },
            { min: 2, max: 40, message: '长度需在 2-40 个字符之间' },
            { pattern: /^[a-zA-Z0-9_-]+$/, message: '仅支持字母、数字、下划线和中划线' },
          ]}
          extra="用户 ID 唯一，登录与案件归属都使用它"
        >
          <Input prefix={<UserOutlined />} placeholder="如：alice_2024" />
        </Form.Item>

        <Form.Item name="name" label="昵称（选填）" rules={[{ max: 20, message: '昵称最长 20 个字符' }]}>
          <Input prefix={<SmileOutlined />} placeholder="展示用昵称，默认同用户 ID" />
        </Form.Item>

        <Form.Item
          name="password"
          label="密码"
          rules={[{ required: true, message: '请输入密码' }, { min: 6, message: '密码至少 6 位' }]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="至少 6 位" />
        </Form.Item>

        <Form.Item
          name="confirm"
          label="确认密码"
          dependencies={['password']}
          rules={[
            { required: true, message: '请再次输入密码' },
            ({ getFieldValue }) => ({
              validator(_, value) {
                if (!value || getFieldValue('password') === value) return Promise.resolve();
                return Promise.reject(new Error('两次输入的密码不一致'));
              },
            }),
          ]}
        >
          <Input.Password prefix={<LockOutlined />} placeholder="再次输入密码" />
        </Form.Item>

        <Form.Item style={{ marginBottom: 12 }}>
          <Button type="primary" htmlType="submit" loading={submitting} block>
            注册并登录
          </Button>
        </Form.Item>
      </Form>
      <div style={{ textAlign: 'center' }}>
        <Typography.Text type="secondary">已有账号？</Typography.Text>{' '}
        <Link to="/login">去登录</Link>
      </div>
    </AuthShell>
  );
}
