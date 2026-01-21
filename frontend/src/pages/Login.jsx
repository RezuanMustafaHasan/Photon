import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [remember, setRemember] = useState(true);
  const [status, setStatus] = useState({ type: 'idle', message: '' });

  const onSubmit = async (e) => {
    e.preventDefault();
    setStatus({ type: 'loading', message: '' });

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        throw new Error(data?.message || 'Login failed.');
      }

      login({ token: data.token, user: data.user, remember });
      navigate('/dashboard');
    } catch (err) {
      setStatus({ type: 'error', message: err?.message || 'Login failed.' });
    }
  };

  return (
    <div className="min-h-screen d-flex align-items-center justify-content-center px-3" style={{ backgroundColor: '#FFF7ED' }}>
      <main className="container" style={{ maxWidth: 520 }}>
        <div className="bg-white border border-gray-100 rounded-2xl p-4 p-sm-5 shadow-sm">
          <div className="d-flex align-items-center justify-content-between mb-4">
            <div className="d-flex align-items-center gap-2">
              <div className="rounded-3 bg-gradient-logo d-flex align-items-center justify-content-center text-white fw-bold shadow-sm" style={{ width: '2rem', height: '2rem' }}>
                P
              </div>
              <div>
                <div className="fw-bold text-primary">Welcome back</div>
                <div className="text-secondary small font-bangla">আবার শুরু করি</div>
              </div>
            </div>
            <Link to="/landing" className="small text-secondary text-decoration-none">
              Back
            </Link>
          </div>

          <form onSubmit={onSubmit} className="d-grid gap-3">
            <div>
              <label className="form-label text-secondary small mb-1">Email</label>
              <input
                type="email"
                className="form-control rounded-3 border-gray-200"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
              />
            </div>

            <div>
              <label className="form-label text-secondary small mb-1">Password</label>
              <input
                type="password"
                className="form-control rounded-3 border-gray-200"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
              />
            </div>

            <div className="d-flex align-items-center justify-content-between">
              <label className="d-flex align-items-center gap-2 small text-secondary">
                <input
                  type="checkbox"
                  className="form-check-input m-0"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                />
                Remember me
              </label>
              <Link to="/signup" className="small text-decoration-none" style={{ color: '#F97316' }}>
                Create account
              </Link>
            </div>

            {status.type === 'error' && (
              <div className="bg-red-50 border border-red-100 rounded-3 p-3 text-red-700 small">
                {status.message}
              </div>
            )}

            <button
              type="submit"
              disabled={status.type === 'loading'}
              className="btn custom-gradient-btn text-white fw-bold rounded-pill py-2 hover-translate-y"
            >
              {status.type === 'loading' ? 'Signing in…' : 'Sign In'}
            </button>
          </form>

          <div className="mt-4 text-center text-secondary small font-bangla">
            লগইন করলে আপনি Dashboard এবং Chapter Chat অ্যাক্সেস করতে পারবেন।
          </div>
        </div>
      </main>
    </div>
  );
};

export default Login;

