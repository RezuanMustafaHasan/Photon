import React from 'react';

const Navbar = () => {
  return (
    <nav className="flex items-center justify-between px-6 py-4 bg-white border-b border-gray-100 shadow-sm sticky top-0 z-50">
      {/* Left: Logo */}
      <div className="flex items-center gap-2">
        <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-cta-start to-cta-end flex items-center justify-center text-white font-bold shadow-md">
          P
        </div>
        <span className="text-xl font-bold text-primary tracking-tight">Photon</span>
      </div>

      {/* Center: Nav Items */}
      <div className="hidden md:flex items-center gap-1 bg-gray-50 p-1.5 rounded-full border border-gray-100">
        <NavItem active>Dashboard</NavItem>
        <NavItem>Admission</NavItem>
        <NavItem>Revision</NavItem>
        <NavItem>Exam</NavItem>
      </div>

      {/* Right: User */}
      <div className="flex items-center gap-4">
        <span className="hidden sm:block text-sm font-medium text-secondary">Hi, Hasan</span>
        <button className="px-4 py-1.5 text-sm font-medium text-secondary border border-gray-200 rounded-full hover:bg-gray-50 transition-colors">
          Logout
        </button>
      </div>
    </nav>
  );
};

const NavItem = ({ children, active }) => (
  <button
    className={`px-5 py-1.5 rounded-full text-sm font-medium transition-all duration-200 ${
      active
        ? 'bg-primary text-white shadow-md'
        : 'text-secondary hover:bg-white hover:text-primary hover:shadow-sm'
    }`}
  >
    {children}
  </button>
);

export default Navbar;
