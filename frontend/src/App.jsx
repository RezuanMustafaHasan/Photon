import React from 'react';
import { Routes, Route, useNavigate, useParams, Navigate } from 'react-router-dom';
import { useAuth } from './auth/AuthContext.jsx';
import Dashboard from './pages/Dashboard';
import ChapterChat from './pages/ChapterChat';
import ExamPage from './pages/ExamPage';
import LandingPage from './pages/LandingPage';
import Login from './pages/Login';
import Signup from './pages/Signup';
import RateLimitScreen from './components/RateLimitScreen';

function ChapterChatRoute() {
  const navigate = useNavigate();
  const { chapterTitle } = useParams();

  const handleBack = () => {
    navigate('/dashboard');
  };

  return (
    <ChapterChat
      chapterTitle={chapterTitle ? decodeURIComponent(chapterTitle) : 'Chapter'}
      onBack={handleBack}
    />
  );
}

function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  if (!isAuthenticated) {
    return <Navigate to="/landing" replace />;
  }
  return children;
}

function HomeRedirect() {
  const { isAuthenticated } = useAuth();
  return <Navigate to={isAuthenticated ? '/dashboard' : '/landing'} replace />;
}

function App() {
  const navigate = useNavigate();
  const { rateLimitNotice } = useAuth();

  if (rateLimitNotice) {
    return <RateLimitScreen notice={rateLimitNotice} />;
  }

  const handleLogin = () => {
    navigate('/dashboard');
  };

  const handleChapterClick = (chapterTitle) => {
    navigate(`/chapter/${encodeURIComponent(chapterTitle)}`);
  };

  return (
    <Routes>
      <Route path="/" element={<HomeRedirect />} />
      <Route path="/landing" element={<LandingPage onLogin={handleLogin} />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard onChapterClick={handleChapterClick} />
          </ProtectedRoute>
        }
      />
      <Route
        path="/chapter/:chapterTitle"
        element={
          <ProtectedRoute>
            <ChapterChatRoute />
          </ProtectedRoute>
        }
      />
      <Route
        path="/exam"
        element={
          <ProtectedRoute>
            <ExamPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
