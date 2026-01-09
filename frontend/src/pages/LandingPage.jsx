import React from 'react';

const LandingPage = ({ onLogin }) => {
  return (
    <div className="min-h-screen d-flex flex-column font-inter" style={{ backgroundColor: '#FFFBF0' }}>
      {/* Navbar */}
      <nav className="navbar navbar-expand-lg py-4 container-xl">
        <div className="container-fluid px-0">
          <a className="navbar-brand d-flex align-items-center gap-2" href="#">
            <div className="rounded-circle bg-gradient-logo d-flex align-items-center justify-content-center text-white fw-bold" style={{ width: '32px', height: '32px' }}>
              P
            </div>
            <span className="fw-bold fs-4 text-primary">Photon</span>
          </a>
          
          <button className="navbar-toggler border-0" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
            <span className="navbar-toggler-icon"></span>
          </button>
          
          <div className="collapse navbar-collapse justify-content-end" id="navbarNav">
            <ul className="navbar-nav align-items-center gap-4">
              <li className="nav-item">
                <a className="nav-link text-secondary fw-medium" href="#">Features</a>
              </li>
              <li className="nav-item">
                <a className="nav-link text-secondary fw-medium" href="#">Pricing</a>
              </li>
              <li className="nav-item">
                <a className="nav-link text-secondary fw-medium" href="#">About</a>
              </li>
              <li className="nav-item">
                <a className="nav-link text-secondary fw-medium" href="#">Contact</a>
              </li>
              <li className="nav-item ms-lg-2">
                <button 
                  onClick={onLogin}
                  className="btn btn-outline-warning text-dark fw-semibold border-2 rounded-pill px-4 py-2 hover-translate-y"
                  style={{ borderColor: '#FDBA74' }}
                >
                  Sign In
                </button>
              </li>
              <li className="nav-item">
                <button 
                  onClick={onLogin}
                  className="btn custom-gradient-btn text-white fw-bold rounded-pill px-4 py-2 hover-translate-y"
                >
                  Start Free Trial
                </button>
              </li>
            </ul>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <main className="flex-grow-1 d-flex align-items-center justify-content-center py-5">
        <div className="container-xl text-center">
          
          {/* Badges */}
          <div className="d-flex flex-wrap justify-content-center align-items-center gap-3 mb-5">
            <div className="badge bg-white text-secondary border border-gray-200 rounded-pill px-3 py-2 d-flex align-items-center gap-2 shadow-sm fw-normal">
              <span className="text-secondary small">Backed by</span>
              <span className="fw-bold" style={{ color: '#F06529' }}>Y Combinator</span>
            </div>
            
            <div className="badge bg-white text-secondary border border-gray-200 rounded-pill px-3 py-2 d-flex align-items-center gap-2 shadow-sm fw-normal">
              <span className="badge bg-danger rounded-1 px-1 me-1" style={{ fontSize: '0.6rem' }}>FEATURED ON</span>
              <span className="fw-bold text-dark">Launch YC</span>
              <span className="text-danger fw-bold ms-1">193</span>
            </div>

            <div className="badge bg-white text-secondary border border-gray-200 rounded-pill px-3 py-2 d-flex align-items-center gap-2 shadow-sm fw-normal">
              <span className="d-flex align-items-center justify-content-center bg-primary rounded-circle text-white" style={{ width: '16px', height: '16px', fontSize: '10px' }}>AI</span>
              <span className="fw-bold text-dark">AI in Education Partner</span>
            </div>
          </div>

          {/* Headline */}
          <h1 className="display-2 fw-bold text-primary mb-4 tracking-tight" style={{ fontSize: '4.5rem', lineHeight: '1.1' }}>
            Understand PHYSICS in<br />
            <span className="text-gradient-custom">minutes</span>, not hours
          </h1>

          {/* Subheadline */}
          <p className="lead text-secondary mb-5 mx-auto" style={{ maxWidth: '600px', fontSize: '1.25rem' }}>
            Let us handle the grading so you can focus on your students.
            Save 90% of your grading time and give students better, faster feedback.
          </p>

          {/* CTA Buttons */}
          <div className="d-flex justify-content-center gap-3">
            <button 
              onClick={onLogin}
              className="btn custom-gradient-btn text-white fw-bold rounded-pill px-5 py-3 fs-5 hover-translate-y"
            >
              Try Photon Free
            </button>
            <button 
              className="btn bg-white text-warning fw-bold border-2 rounded-pill px-5 py-3 fs-5 hover-translate-y shadow-sm"
              style={{ borderColor: '#FDBA74', color: '#F97316' }}
            >
              Watch Demo
            </button>
          </div>

        </div>
      </main>
    </div>
  );
};

export default LandingPage;
