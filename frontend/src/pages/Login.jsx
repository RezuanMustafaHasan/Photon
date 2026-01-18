import React, { useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';

const isValidEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const Login = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAuth();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);

  const [touched, setTouched] = useState({ email: false, password: false });
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState('');

  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:5000';

  const errors = useMemo(() => {
    const next = {};
    if (!email.trim()) next.email = 'Email is required.';
    else if (!isValidEmail(email.trim())) next.email = 'Enter a valid email address.';
    if (!password) next.password = 'Password is required.';
    return next;
  }, [email, password]);

  const canSubmit = Object.keys(errors).length === 0 && !submitting;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setTouched({ email: true, password: true });
    setServerError('');
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      const res = await fetch(`${apiBase}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim(), password }),
      });

      if (!res.ok) {
        let message = 'Login failed.';
        try {
          const data = await res.json();
          if (data?.message) message = data.message;
        } catch {
          message = 'Login failed.';
        }
        setServerError(message);
        return;
      }

      const data = await res.json();
      if (!data?.token || !data?.user) {
        setServerError('Login failed.');
        return;
      }

      await sleep(250);
      auth.login({ token: data.token, user: data.user, remember: rememberMe });

      const from = location.state?.from?.pathname || '/dashboard';
      navigate(from, { replace: true });
    } catch {
      setServerError('Unable to reach the server. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="auth-shell min-h-screen d-flex align-items-center py-5">
      <div className="container">
        <div className="row justify-content-center">
          <div className="col-12 col-sm-10 col-md-8 col-lg-5">
            <div className="auth-card bg-white border border-gray-100 rounded-2xl p-4 p-sm-5 shadow-sm">
              <div className="d-flex align-items-center justify-content-center mb-4">
                <div className="rounded-3 bg-gradient-logo d-flex align-items-center justify-content-center text-white fw-bold shadow-sm me-2" style={{ width: '2.25rem', height: '2.25rem' }}>
                  P
                </div>
                <span className="fs-4 fw-bold text-primary tracking-tight">Photon</span>
              </div>

              <h1 className="h3 fw-bold text-primary text-center mb-2">Welcome back</h1>
              <p className="text-secondary text-center mb-4">Login to continue learning faster.</p>

              {serverError ? (
                <div className="alert alert-danger py-2" role="alert" aria-live="polite">
                  {serverError}
                </div>
              ) : null}

              <form onSubmit={handleSubmit} noValidate>
                <div className="mb-3">
                  <label htmlFor="loginEmail" className="form-label fw-semibold text-primary">
                    Email
                  </label>
                  <input
                    id="loginEmail"
                    type="email"
                    className={`form-control auth-input ${touched.email && errors.email ? 'is-invalid' : ''}`}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onBlur={() => setTouched((t) => ({ ...t, email: true }))}
                    autoComplete="email"
                    inputMode="email"
                    aria-invalid={Boolean(touched.email && errors.email)}
                    aria-describedby={touched.email && errors.email ? 'loginEmailError' : undefined}
                    disabled={submitting}
                    required
                  />
                  {touched.email && errors.email ? (
                    <div id="loginEmailError" className="invalid-feedback">
                      {errors.email}
                    </div>
                  ) : null}
                </div>

                <div className="mb-3">
                  <label htmlFor="loginPassword" className="form-label fw-semibold text-primary">
                    Password
                  </label>
                  <input
                    id="loginPassword"
                    type="password"
                    className={`form-control auth-input ${touched.password && errors.password ? 'is-invalid' : ''}`}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                    autoComplete="current-password"
                    aria-invalid={Boolean(touched.password && errors.password)}
                    aria-describedby={touched.password && errors.password ? 'loginPasswordError' : undefined}
                    disabled={submitting}
                    required
                  />
                  {touched.password && errors.password ? (
                    <div id="loginPasswordError" className="invalid-feedback">
                      {errors.password}
                    </div>
                  ) : null}
                </div>

                <div className="d-flex align-items-center justify-content-between mb-4">
                  <div className="form-check">
                    <input
                      id="rememberMe"
                      className="form-check-input"
                      type="checkbox"
                      checked={rememberMe}
                      onChange={(e) => setRememberMe(e.target.checked)}
                      disabled={submitting}
                    />
                    <label className="form-check-label text-secondary" htmlFor="rememberMe">
                      Remember me
                    </label>
                  </div>

                  <Link to="/forgot-password" className="auth-link fw-semibold">
                    Forgot password?
                  </Link>
                </div>

                <button type="submit" className="btn auth-primary-btn w-100 rounded-pill py-2 fw-bold" disabled={!canSubmit}>
                  {submitting ? (
                    <span className="d-inline-flex align-items-center justify-content-center gap-2">
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                      Logging in
                    </span>
                  ) : (
                    'Login'
                  )}
                </button>

                <div className="text-center mt-4 text-secondary">
                  New here?{' '}
                  <Link to="/signup" className="auth-link fw-bold">
                    Create an account
                  </Link>
                </div>
              </form>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;
