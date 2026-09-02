import { Routes, Route, Navigate } from 'react-router-dom';
import AppLayout from './components/AppLayout';
import HomePage from './pages/HomePage';
import CreateCasePage from './pages/CreateCasePage';
import ChatPage from './pages/ChatPage';
import VerdictPage from './pages/VerdictPage';
import HistoryPage from './pages/HistoryPage';

export default function App() {
  return (
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/" element={<HomePage />} />
        <Route path="/create" element={<CreateCasePage />} />
        <Route path="/chat/:caseId" element={<ChatPage />} />
        <Route path="/verdict/:caseId" element={<VerdictPage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
