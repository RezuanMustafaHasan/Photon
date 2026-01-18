import React from 'react';
import { useNavigate } from 'react-router-dom';

const LandingPage = () => {
  const navigate = useNavigate();
  const scrollToId = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };
  return (
    <div className="min-h-screen d-flex flex-column font-inter" style={{ backgroundColor: '#FFFBF0' }}>
      {/* Navbar */}
      <nav className="navbar navbar-expand-lg py-4 container-xl">
        <div className="container-fluid px-0">
          <a className="navbar-brand d-flex align-items-center gap-2" href="/" onClick={(e) => { e.preventDefault(); scrollToId('top'); }}>
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
                <a className="nav-link text-secondary fw-medium" href="#features" onClick={(e) => { e.preventDefault(); scrollToId('features'); }}>
                  Features
                </a>
              </li>
              <li className="nav-item">
                <a className="nav-link text-secondary fw-medium" href="#pricing" onClick={(e) => { e.preventDefault(); scrollToId('pricing'); }}>
                  Pricing
                </a>
              </li>
              <li className="nav-item">
                <a className="nav-link text-secondary fw-medium" href="#about" onClick={(e) => { e.preventDefault(); scrollToId('about'); }}>
                  About
                </a>
              </li>
              <li className="nav-item">
                <a className="nav-link text-secondary fw-medium" href="#contact" onClick={(e) => { e.preventDefault(); scrollToId('contact'); }}>
                  Contact
                </a>
              </li>
              <li className="nav-item ms-lg-2">
                <button 
                  onClick={() => navigate('/login')}
                  className="btn btn-outline-warning text-dark fw-semibold border-2 rounded-pill px-4 py-2 hover-translate-y"
                  style={{ borderColor: '#FDBA74' }}
                >
                  Sign In
                </button>
              </li>
              <li className="nav-item">
                <button 
                  onClick={() => navigate('/signup')}
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
      <main id="top" className="flex-grow-1 d-flex align-items-center justify-content-center py-5 scroll-section">
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
              onClick={() => navigate('/signup')}
              className="btn custom-gradient-btn text-white fw-bold rounded-pill px-5 py-3 fs-5 hover-translate-y"
            >
              Try Photon Free
            </button>
            <button 
              type="button"
              onClick={() => scrollToId('features')}
              className="btn bg-white text-warning fw-bold border-2 rounded-pill px-5 py-3 fs-5 hover-translate-y shadow-sm"
              style={{ borderColor: '#FDBA74', color: '#F97316' }}
            >
              Watch Demo
            </button>
          </div>

        </div>
      </main>

      <section id="features" className="py-5 scroll-section">
        <div className="container-xl">
          <div className="text-center mb-5">
            <h2 className="fw-bold text-primary mb-2">Features</h2>
            <p className="text-secondary mx-auto" style={{ maxWidth: '680px' }}>
              Built for fast understanding: concise explanations, targeted practice, and clear progress.
            </p>
          </div>

          <div className="row g-4">
            <div className="col-12 col-md-4">
              <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm h-100 card-hover-effect">
                <div className="d-inline-flex align-items-center justify-content-center rounded-circle bg-orange-50 border border-orange-100 mb-3" style={{ width: '44px', height: '44px' }}>
                  <span className="fw-bold" style={{ color: '#F97316' }}>AI</span>
                </div>
                <h3 className="h5 fw-bold text-primary">Instant explanations</h3>
                <p className="text-secondary mb-0">
                  Get clear answers and step-by-step reasoning when you’re stuck.
                </p>
              </div>
            </div>
            <div className="col-12 col-md-4">
              <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm h-100 card-hover-effect">
                <div className="d-inline-flex align-items-center justify-content-center rounded-circle bg-orange-50 border border-orange-100 mb-3" style={{ width: '44px', height: '44px' }}>
                  <span className="fw-bold" style={{ color: '#F97316' }}>Q</span>
                </div>
                <h3 className="h5 fw-bold text-primary">Practice that adapts</h3>
                <p className="text-secondary mb-0">
                  Focus on weak areas with guided questions and quick feedback.
                </p>
              </div>
            </div>
            <div className="col-12 col-md-4">
              <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm h-100 card-hover-effect">
                <div className="d-inline-flex align-items-center justify-content-center rounded-circle bg-orange-50 border border-orange-100 mb-3" style={{ width: '44px', height: '44px' }}>
                  <span className="fw-bold" style={{ color: '#F97316' }}>✓</span>
                </div>
                <h3 className="h5 fw-bold text-primary">Track progress</h3>
                <p className="text-secondary mb-0">
                  See what you’ve mastered and what to revise next.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="pricing" className="py-5 scroll-section">
        <div className="container-xl">
          <div className="text-center mb-5">
            <h2 className="fw-bold text-primary mb-2">Pricing</h2>
            <p className="text-secondary mx-auto" style={{ maxWidth: '680px' }}>
              Start free and upgrade when you’re ready.
            </p>
          </div>

          <div className="row g-4 justify-content-center">
            <div className="col-12 col-md-6 col-lg-4">
              <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm h-100 card-hover-effect">
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <h3 className="h5 fw-bold text-primary mb-0">Free</h3>
                  <span className="badge bg-orange-50 border border-orange-100 text-primary rounded-pill px-3 py-2">Starter</span>
                </div>
                <div className="display-6 fw-bold text-primary mb-3">$0</div>
                <ul className="text-secondary mb-4 ps-3">
                  <li className="mb-2">Core explanations</li>
                  <li className="mb-2">Practice prompts</li>
                  <li className="mb-2">Progress overview</li>
                </ul>
                <button type="button" onClick={() => navigate('/signup')} className="btn auth-primary-btn w-100 rounded-pill py-2 fw-bold">
                  Start Free
                </button>
              </div>
            </div>

            <div className="col-12 col-md-6 col-lg-4">
              <div className="bg-white border border-orange-100 rounded-2xl p-4 shadow-sm h-100 card-hover-effect position-relative overflow-hidden">
                <div className="position-absolute top-0 end-0 m-3 badge text-white rounded-pill px-3 py-2" style={{ background: 'linear-gradient(to right, var(--color-cta-start), var(--color-cta-end))' }}>
                  Popular
                </div>
                <div className="d-flex align-items-center justify-content-between mb-2">
                  <h3 className="h5 fw-bold text-primary mb-0">Pro</h3>
                  <span className="badge bg-orange-50 border border-orange-100 text-primary rounded-pill px-3 py-2">Best value</span>
                </div>
                <div className="display-6 fw-bold text-primary mb-3">$9</div>
                <ul className="text-secondary mb-4 ps-3">
                  <li className="mb-2">Everything in Free</li>
                  <li className="mb-2">Deeper explanations</li>
                  <li className="mb-2">Faster revision flow</li>
                </ul>
                <button type="button" onClick={() => navigate('/signup')} className="btn auth-primary-btn w-100 rounded-pill py-2 fw-bold">
                  Start Pro Trial
                </button>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="about" className="py-5 scroll-section">
        <div className="container-xl">
          <div className="row align-items-center g-4">
            <div className="col-12 col-lg-6">
              <h2 className="fw-bold text-primary mb-3">About Photon</h2>
              <p className="text-secondary leading-relaxed mb-3">
                Photon helps you understand physics quickly with focused explanations and practice that targets your weak points.
              </p>
              <p className="text-secondary leading-relaxed mb-0">
                The goal is simple: <span className="fw-semibold text-primary">minutes, not hours</span>.
              </p>
            </div>
            <div className="col-12 col-lg-6">
              <div className="bg-white border border-gray-100 rounded-2xl p-4 shadow-sm">
                <div className="d-flex align-items-center gap-3">
                  <div className="rounded-3 bg-gradient-logo d-flex align-items-center justify-content-center text-white fw-bold" style={{ width: '44px', height: '44px' }}>
                    P
                  </div>
                  <div>
                    <div className="fw-bold text-primary">Understand physics in minutes</div>
                    <div className="text-secondary text-sm">Learn faster with guided steps</div>
                  </div>
                </div>
                <div className="mt-4 d-flex gap-2 flex-wrap">
                  <span className="badge bg-orange-50 border border-orange-100 text-primary rounded-pill px-3 py-2">AI Tutor</span>
                  <span className="badge bg-orange-50 border border-orange-100 text-primary rounded-pill px-3 py-2">Progress</span>
                  <span className="badge bg-orange-50 border border-orange-100 text-primary rounded-pill px-3 py-2">Revision</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="contact" className="py-5 scroll-section">
        <div className="container-xl">
          <div className="bg-white border border-gray-100 rounded-2xl p-4 p-sm-5 shadow-sm text-center">
            <h2 className="fw-bold text-primary mb-2">Contact</h2>
            <p className="text-secondary mb-4 mx-auto" style={{ maxWidth: '680px' }}>
              Questions or feedback? We’d love to hear from you.
            </p>
            <div className="d-flex justify-content-center gap-3 flex-wrap">
              <a className="btn btn-outline-warning text-dark fw-semibold border-2 rounded-pill px-4 py-2 hover-translate-y" style={{ borderColor: '#FDBA74' }} href="mailto:hello@photon.app">
                Email us
              </a>
              <button type="button" onClick={() => navigate('/signup')} className="btn auth-primary-btn rounded-pill px-4 py-2 fw-bold hover-translate-y">
                Get Started
              </button>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};

export default LandingPage;
