import React from 'react';
import { Routes, Route, useNavigate, useParams, Navigate } from 'react-router-dom';
import { useAuth } from './auth/AuthContext.jsx';
import Dashboard from './pages/Dashboard';
import ChapterChat from './pages/ChapterChat';
import LandingPage from './pages/LandingPage';
import Login from './pages/Login';
import Signup from './pages/Signup';

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
  const { isAuthenticated, isHydrating } = useAuth();
  if (isHydrating) {
    return (
      <div className="min-h-screen d-flex align-items-center justify-content-center" style={{ backgroundColor: '#FFF7ED' }}>
        <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm text-center">
          <div className="fw-bold text-primary mb-1">Loading…</div>
          <div className="text-secondary small">Checking your session</div>
        </div>
      </div>
    );
  }
  if (!isAuthenticated) {
    return <Navigate to="/landing" replace />;
  }
  return children;
}

function HomeRedirect() {
  const { isAuthenticated, isHydrating } = useAuth();
  if (isHydrating) {
    return (
      <div className="min-h-screen d-flex align-items-center justify-content-center" style={{ backgroundColor: '#FFF7ED' }}>
        <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm text-center">
          <div className="fw-bold text-primary mb-1">Loading…</div>
          <div className="text-secondary small">Checking your session</div>
        </div>
      </div>
    );
  }
  return <Navigate to={isAuthenticated ? '/dashboard' : '/landing'} replace />;
}

function App() {
  const navigate = useNavigate();

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
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
