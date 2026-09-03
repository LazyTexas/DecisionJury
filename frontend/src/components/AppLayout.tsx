import { Outlet, useNavigate } from 'react-router-dom';
import { Layout, Typography, Button, Space, Dropdown, Avatar } from 'antd';
import { PlusOutlined, HomeOutlined, UserOutlined, LogoutOutlined } from '@ant-design/icons';
import { useAuth } from '../auth/AuthContext';

const { Header, Content } = Layout;

export default function AppLayout() {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  const handleLogout = () => {
    logout();
    navigate('/login', { replace: true });
  };

  const userMenu = {
    items: [
      {
        key: 'logout',
        icon: <LogoutOutlined />,
        label: '退出登录',
        onClick: handleLogout,
      },
    ],
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header
        style={{
          background: '#fff',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '0 24px',
          borderBottom: '1px solid #f0f0f0',
          position: 'sticky',
          top: 0,
          zIndex: 100,
          height: 56,
          lineHeight: '56px',
        }}
      >
        <Space>
          <HomeOutlined
            style={{ fontSize: 20, cursor: 'pointer', color: '#1677ff' }}
            onClick={() => navigate('/')}
          />
          <Typography.Title level={4} style={{ margin: 0, cursor: 'pointer' }} onClick={() => navigate('/')}>
            DecisionJury
          </Typography.Title>
        </Space>
        <Space size="middle">
          <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/create')}>
            新建决策
          </Button>
          {user && (
            <Dropdown menu={userMenu} placement="bottomRight">
              <Space style={{ cursor: 'pointer' }}>
                <Avatar size="small" style={{ background: '#1677ff' }} icon={<UserOutlined />} />
                <Typography.Text style={{ maxWidth: 140, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {user.name || user.user_id}
                </Typography.Text>
              </Space>
            </Dropdown>
          )}
        </Space>
      </Header>
      <Content style={{ padding: '24px', maxWidth: 960, width: '100%', margin: '0 auto' }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
