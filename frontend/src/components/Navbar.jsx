import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext.jsx';

const Navbar = () => {
  const navigate = useNavigate();
  const { user, logout } = useAuth();

  return (
    <nav className="d-flex align-items-center justify-content-between px-4 py-3 bg-white border-bottom border-gray-100 shadow-sm sticky-top z-50">
      {/* Left: Logo */}
      <button
        type="button"
        onClick={() => navigate('/dashboard')}
        className="d-flex align-items-center gap-2 border-0 bg-transparent p-0"
      >
        <div className="rounded-3 bg-gradient-logo d-flex align-items-center justify-content-center text-white fw-bold shadow-sm" style={{ width: '2rem', height: '2rem' }}>
          P
        </div>
        <span className="fs-5 fw-bold text-primary tracking-tight">Photon</span>
      </button>

      {/* Center: Nav Items */}
      <div className="d-none d-md-flex align-items-center gap-1 bg-gray-50 p-1 rounded-pill border border-gray-100">
        <NavItem active>Dashboard</NavItem>
        <NavItem>Admission</NavItem>
        <NavItem>Revision</NavItem>
        <NavItem>Exam</NavItem>
      </div>

      {/* Right: User */}
      <div className="d-flex align-items-center gap-4">
        <span className="d-none d-sm-block small fw-medium text-secondary">
          Hi, {user?.name || 'Student'}
        </span>
        <button
          type="button"
          onClick={() => {
            logout();
            navigate('/landing');
          }}
          className="px-4 py-1 small fw-medium text-secondary border border-gray-200 rounded-pill bg-white hover-bg-gray-50 transition-colors"
        >
          Logout
        </button>
      </div>
    </nav>
  );
};

const NavItem = ({ children, active }) => (
  <button
    className={`px-4 py-1 rounded-pill small fw-medium border-0 transition-all duration-200 ${
      active
        ? 'bg-primary text-white shadow-sm'
        : 'bg-transparent text-secondary hover-bg-white hover-text-primary hover-shadow-sm'
    }`}
  >
    {children}
  </button>
);

export default Navbar;
