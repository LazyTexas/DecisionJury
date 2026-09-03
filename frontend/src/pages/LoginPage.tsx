// ============================================================
// 登录页
// 调用 POST /api/auth/login，成功后把 {user_id, name} 写入
// localStorage（AuthContext 内部处理），跳回原目标页或首页。
// ============================================================

import { useState } from 'react';
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom';
import { Form, Input, Button, message, Typography } from 'antd';
import { UserOutlined, LockOutlined } from '@ant-design/icons';
import { useAuth } from '../auth/AuthContext';
import AuthShell from '../auth/AuthShell';

export default function LoginPage() {
  const { user, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [submitting, setSubmitting] = useState(false);

  // 已登录访问登录页 → 直接回首页
  if (user) {
    return <Navigate to="/" replace />;
  }

  // RequireAuth 重定向时带来的来源页（state.from），登录后跳回去
  const from = (location.state as { from?: string } | null)?.from;

  const handleFinish = async (values: { user_id: string; password: string }) => {
    setSubmitting(true);
    try {
      await login(values.user_id.trim(), values.password);
      message.success('登录成功');
      navigate(from && from !== '/login' ? from : '/', { replace: true });
    } catch (err: any) {
      message.error(err.message || '登录失败，请重试');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell title="登录" subtitle="冷静决策助手，登录后继续你的决策旅程">
      <Form layout="vertical" onFinish={handleFinish} requiredMark={false} size="large">
        <Form.Item
          name="user_id"
          label="用户 ID"
          rules={[{ required: true, message: '请输入用户 ID' }, { whitespace: true, message: '不能为空格' }]}
        >
          <Input prefix={<UserOutlined />} placeholder="你的用户 ID（自定义，将用于关联案件）" maxLength={40} />
        </Form.Item>

        <Form.Item name="password" label="密码" rules={[{ required: true, message: '请输入密码' }]}>
          <Input.Password prefix={<LockOutlined />} placeholder="请输入密码" />
        </Form.Item>

        <Form.Item style={{ marginBottom: 12 }}>
          <Button type="primary" htmlType="submit" loading={submitting} block>
            登录
          </Button>
        </Form.Item>
      </Form>
      <div style={{ textAlign: 'center' }}>
        <Typography.Text type="secondary">还没有账号？</Typography.Text>{' '}
        <Link to="/register">立即注册</Link>
      </div>
    </AuthShell>
  );
}
