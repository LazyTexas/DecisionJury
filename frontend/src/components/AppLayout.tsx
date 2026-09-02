import { Outlet, useNavigate } from 'react-router-dom';
import { Layout, Typography, Button, Space } from 'antd';
import { PlusOutlined, HomeOutlined } from '@ant-design/icons';

const { Header, Content } = Layout;

export default function AppLayout() {
  const navigate = useNavigate();

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
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/create')}>
          新建决策
        </Button>
      </Header>
      <Content style={{ padding: '24px', maxWidth: 960, width: '100%', margin: '0 auto' }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
