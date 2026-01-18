import React, { useMemo, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';

const isValidEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

const getPasswordStrength = (password) => {
  const value = password || '';
  let score = 0;
  if (value.length >= 8) score += 1;
  if (/[A-Z]/.test(value)) score += 1;
  if (/[0-9]/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value)) score += 1;

  const percent = (score / 4) * 100;
  const label = score <= 1 ? 'Weak' : score === 2 ? 'Fair' : score === 3 ? 'Good' : 'Strong';
  const barClass = score <= 1 ? 'bg-danger' : score === 2 ? 'bg-warning' : score === 3 ? 'bg-info' : 'bg-success';

  return { score, percent, label, barClass };
};

const Signup = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAuth();

  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [serverError, setServerError] = useState('');
  const [touched, setTouched] = useState({ fullName: false, email: false, password: false, confirmPassword: false });

  const apiBase = import.meta.env.VITE_API_URL || 'http://localhost:5000';
  const strength = useMemo(() => getPasswordStrength(password), [password]);

  const errors = useMemo(() => {
    const next = {};
    if (!fullName.trim()) next.fullName = 'Full name is required.';
    else if (fullName.trim().length < 2) next.fullName = 'Full name is too short.';

    if (!email.trim()) next.email = 'Email is required.';
    else if (!isValidEmail(email.trim())) next.email = 'Enter a valid email address.';

    if (!password) next.password = 'Password is required.';
    else if (password.length < 8) next.password = 'Password must be at least 8 characters.';

    if (!confirmPassword) next.confirmPassword = 'Please confirm your password.';
    else if (confirmPassword !== password) next.confirmPassword = 'Passwords do not match.';

    return next;
  }, [fullName, email, password, confirmPassword]);

  const canSubmit = Object.keys(errors).length === 0 && !submitting;

  const handleSubmit = async (e) => {
    e.preventDefault();
    setTouched({ fullName: true, email: true, password: true, confirmPassword: true });
    setServerError('');
    if (Object.keys(errors).length > 0) return;

    setSubmitting(true);
    try {
      const res = await fetch(`${apiBase}/api/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: fullName.trim(), email: email.trim(), password }),
      });

      if (!res.ok) {
        let message = 'Sign up failed.';
        try {
          const data = await res.json();
          if (data?.message) message = data.message;
        } catch {
          message = 'Sign up failed.';
        }
        setServerError(message);
        return;
      }

      const data = await res.json();
      if (!data?.token || !data?.user) {
        setServerError('Sign up failed.');
        return;
      }

      await sleep(250);
      auth.login({ token: data.token, user: data.user, remember: true });

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
          <div className="col-12 col-sm-10 col-md-8 col-lg-6">
            <div className="auth-card bg-white border border-gray-100 rounded-2xl p-4 p-sm-5 shadow-sm">
              <div className="d-flex align-items-center justify-content-center mb-4">
                <div className="rounded-3 bg-gradient-logo d-flex align-items-center justify-content-center text-white fw-bold shadow-sm me-2" style={{ width: '2.25rem', height: '2.25rem' }}>
                  P
                </div>
                <span className="fs-4 fw-bold text-primary tracking-tight">Photon</span>
              </div>

              <h1 className="h3 fw-bold text-primary text-center mb-2">Create your account</h1>
              <p className="text-secondary text-center mb-4">Understand physics in minutes, not hours.</p>

              {serverError ? (
                <div className="alert alert-danger py-2" role="alert" aria-live="polite">
                  {serverError}
                </div>
              ) : null}

              <form onSubmit={handleSubmit} noValidate>
                <div className="mb-3">
                  <label htmlFor="signupName" className="form-label fw-semibold text-primary">
                    Full name
                  </label>
                  <input
                    id="signupName"
                    type="text"
                    className={`form-control auth-input ${touched.fullName && errors.fullName ? 'is-invalid' : ''}`}
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    onBlur={() => setTouched((t) => ({ ...t, fullName: true }))}
                    autoComplete="name"
                    aria-invalid={Boolean(touched.fullName && errors.fullName)}
                    aria-describedby={touched.fullName && errors.fullName ? 'signupNameError' : undefined}
                    disabled={submitting}
                    required
                  />
                  {touched.fullName && errors.fullName ? (
                    <div id="signupNameError" className="invalid-feedback">
                      {errors.fullName}
                    </div>
                  ) : null}
                </div>

                <div className="mb-3">
                  <label htmlFor="signupEmail" className="form-label fw-semibold text-primary">
                    Email
                  </label>
                  <input
                    id="signupEmail"
                    type="email"
                    className={`form-control auth-input ${touched.email && errors.email ? 'is-invalid' : ''}`}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    onBlur={() => setTouched((t) => ({ ...t, email: true }))}
                    autoComplete="email"
                    inputMode="email"
                    aria-invalid={Boolean(touched.email && errors.email)}
                    aria-describedby={touched.email && errors.email ? 'signupEmailError' : undefined}
                    disabled={submitting}
                    required
                  />
                  {touched.email && errors.email ? (
                    <div id="signupEmailError" className="invalid-feedback">
                      {errors.email}
                    </div>
                  ) : null}
                </div>

                <div className="mb-3">
                  <label htmlFor="signupPassword" className="form-label fw-semibold text-primary">
                    Password
                  </label>
                  <input
                    id="signupPassword"
                    type="password"
                    className={`form-control auth-input ${touched.password && errors.password ? 'is-invalid' : ''}`}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    onBlur={() => setTouched((t) => ({ ...t, password: true }))}
                    autoComplete="new-password"
                    aria-invalid={Boolean(touched.password && errors.password)}
                    aria-describedby="passwordHelp"
                    disabled={submitting}
                    required
                  />

                  <div className="mt-2">
                    <div className="d-flex align-items-center justify-content-between">
                      <span id="passwordHelp" className="text-secondary text-sm">
                        Strength: <span className="fw-semibold text-primary">{strength.label}</span>
                      </span>
                      <span className="text-secondary text-xs">{Math.round(strength.percent)}%</span>
                    </div>
                    <div className="progress mt-2" style={{ height: '6px' }} aria-hidden="true">
                      <div className={`progress-bar ${strength.barClass}`} style={{ width: `${strength.percent}%` }} />
                    </div>
                  </div>

                  {touched.password && errors.password ? (
                    <div className="invalid-feedback d-block">{errors.password}</div>
                  ) : null}
                </div>

                <div className="mb-4">
                  <label htmlFor="signupConfirmPassword" className="form-label fw-semibold text-primary">
                    Confirm password
                  </label>
                  <input
                    id="signupConfirmPassword"
                    type="password"
                    className={`form-control auth-input ${touched.confirmPassword && errors.confirmPassword ? 'is-invalid' : ''}`}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    onBlur={() => setTouched((t) => ({ ...t, confirmPassword: true }))}
                    autoComplete="new-password"
                    aria-invalid={Boolean(touched.confirmPassword && errors.confirmPassword)}
                    aria-describedby={touched.confirmPassword && errors.confirmPassword ? 'signupConfirmPasswordError' : undefined}
                    disabled={submitting}
                    required
                  />
                  {touched.confirmPassword && errors.confirmPassword ? (
                    <div id="signupConfirmPasswordError" className="invalid-feedback">
                      {errors.confirmPassword}
                    </div>
                  ) : null}
                </div>

                <button type="submit" className="btn auth-primary-btn w-100 rounded-pill py-2 fw-bold" disabled={!canSubmit}>
                  {submitting ? (
                    <span className="d-inline-flex align-items-center justify-content-center gap-2">
                      <span className="spinner-border spinner-border-sm" role="status" aria-hidden="true" />
                      Creating account
                    </span>
                  ) : (
                    'Sign Up'
                  )}
                </button>

                <div className="text-center mt-4 text-secondary">
                  Already have an account?{' '}
                  <Link to="/login" className="auth-link fw-bold">
                    Login
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

export default Signup;

