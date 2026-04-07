import React from 'react';

const ProgressRing = ({ value, size = 100, strokeWidth = 8 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="position-relative d-flex align-items-center justify-content-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-n90">
        <circle
          stroke="#E2E8F0"
          fill="transparent"
          strokeWidth={strokeWidth}
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          stroke="#22C55E"
          fill="transparent"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          r={radius}
          cx={size / 2}
          cy={size / 2}
          className="transition-all duration-1000 ease-out"
          style={{ transition: 'stroke-dashoffset 1s ease-out' }}
        />
      </svg>
      <div className="position-absolute top-0 start-0 w-100 h-100 d-flex align-items-center justify-content-center">
        <span className="fs-5 fw-bold text-primary">{value}%</span>
      </div>
    </div>
  );
};

const ProgressCard = ({ summary, status, error }) => {
  const overallProgress = Number(summary?.overallProgress) || 0;
  const practicedLessons = Number(summary?.practicedLessons) || 0;
  const completedLessons = Number(summary?.completedLessons) || 0;
  const weakLessons = Number(summary?.weakLessons) || 0;

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 d-flex flex-row align-items-center gap-4 h-100 card-hover-effect">
      <div className="flex-shrink-0">
        <ProgressRing value={overallProgress} />
      </div>
      <div className="flex-1 vstack gap-3 w-100">
        <h3 className="text-lg-custom fw-bold text-primary d-flex align-items-center gap-2">
          📈 Your Progress
        </h3>

        {status === 'loading' && <div className="text-secondary small">Refreshing your mastery progress…</div>}
        {status === 'error' && <div className="text-danger small">{error || 'Progress could not be loaded.'}</div>}

        {status !== 'loading' && status !== 'error' && (
          <div className="vstack gap-2">
            <div className="d-flex justify-content-between small">
              <span className="text-secondary">Syllabus mastery</span>
              <span className="fw-semibold text-primary">{overallProgress}%</span>
            </div>
            <div className="d-flex justify-content-between small">
              <span className="text-secondary">Practiced lessons</span>
              <span className="fw-semibold text-accent">{practicedLessons}</span>
            </div>
            <div className="d-flex justify-content-between small">
              <span className="text-secondary">Completed lessons</span>
              <span className="fw-semibold text-primary">{completedLessons}</span>
            </div>
            <div className="d-flex justify-content-between small">
              <span className="text-secondary">Weak lessons</span>
              <span className="fw-semibold text-primary">{weakLessons}</span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default ProgressCard;
