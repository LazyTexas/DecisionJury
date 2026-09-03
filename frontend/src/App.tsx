import { Routes, Route, Navigate } from 'react-router-dom';
import RequireAuth from './auth/RequireAuth';
import AppLayout from './components/AppLayout';
import LoginPage from './pages/LoginPage';
import RegisterPage from './pages/RegisterPage';
import HomePage from './pages/HomePage';
import CreateCasePage from './pages/CreateCasePage';
import ChatPage from './pages/ChatPage';
import VerdictPage from './pages/VerdictPage';
import HistoryPage from './pages/HistoryPage';

export default function App() {
  return (
    <Routes>
      {/* 认证页：不要求登录；已登录访问会自动跳首页（见页面内逻辑） */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />

      {/* 业务页：RequireAuth 守卫，未登录重定向 /login */}
      <Route element={<RequireAuth><AppLayout /></RequireAuth>}>
        <Route path="/" element={<HomePage />} />
        <Route path="/create" element={<CreateCasePage />} />
        <Route path="/chat/:caseId" element={<ChatPage />} />
        <Route path="/verdict/:caseId" element={<VerdictPage />} />
        <Route path="/history" element={<HistoryPage />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
