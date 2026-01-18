import React from 'react';
import { Routes, Route, useNavigate, useParams, Navigate, useLocation, Link } from 'react-router-dom';
import Dashboard from './pages/Dashboard';
import ChapterChat from './pages/ChapterChat';
import LandingPage from './pages/LandingPage';
import Login from './pages/Login';
import Signup from './pages/Signup';
import { useAuth } from './auth/AuthContext.jsx';

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

function RequireAuth({ children }) {
  const auth = useAuth();
  const location = useLocation();
  if (!auth.isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }
  return children;
}

function ForgotPassword() {
  return (
    <div className="auth-shell min-h-screen d-flex align-items-center py-5">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-12 col-sm-10 col-md-8 col-lg-5">
            <div className="auth-card bg-white border border-gray-100 rounded-2xl p-4 p-sm-5 shadow-sm text-center">
              <div className="d-flex align-items-center justify-content-center mb-4">
                <div className="rounded-3 bg-gradient-logo d-flex align-items-center justify-content-center text-white fw-bold shadow-sm me-2" style={{ width: '2.25rem', height: '2.25rem' }}>
                  P
                </div>
                <span className="fs-4 fw-bold text-primary tracking-tight">Photon</span>
              </div>
              <h1 className="h3 fw-bold text-primary mb-2">Forgot password</h1>
              <p className="text-secondary mb-4">Password reset will be available soon.</p>
              <Link to="/login" className="btn auth-primary-btn rounded-pill px-4 py-2 fw-bold">
                Back to Login
              </Link>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function App() {
  const navigate = useNavigate();

  const handleChapterClick = (chapterTitle) => {
    navigate(`/chapter/${encodeURIComponent(chapterTitle)}`);
  };

  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route path="/forgot-password" element={<ForgotPassword />} />
      <Route
        path="/dashboard"
        element={
          <RequireAuth>
            <Dashboard onChapterClick={handleChapterClick} />
          </RequireAuth>
        }
      />
      <Route
        path="/chapter/:chapterTitle"
        element={
          <RequireAuth>
            <ChapterChatRoute />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;
