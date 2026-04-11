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
  const metrics = [
    { label: 'Syllabus mastery', value: `${overallProgress}%`, valueClassName: 'text-primary' },
    { label: 'Practiced lessons', value: practicedLessons, valueClassName: 'text-accent' },
    { label: 'Completed lessons', value: completedLessons, valueClassName: 'text-primary' },
    { label: 'Weak lessons', value: weakLessons, valueClassName: 'text-primary' },
  ];

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 card-hover-effect">
      <div className="d-flex flex-column flex-lg-row align-items-start align-items-lg-center gap-4">
        <div className="flex-shrink-0 align-self-center align-self-lg-auto">
          <ProgressRing value={overallProgress} />
        </div>

        <div className="flex-grow-1 w-100">
          <h3 className="text-lg-custom fw-bold text-primary mb-3">
            Your Progress
          </h3>

          {status === 'loading' && <div className="text-secondary small">Refreshing your mastery progress…</div>}
          {status === 'error' && <div className="text-danger small">{error || 'Progress could not be loaded.'}</div>}

          {status !== 'loading' && status !== 'error' && (
            <div className="row g-3">
              {metrics.map((metric) => (
                <div key={metric.label} className="col-12 col-sm-6 col-xl-3">
                  <div className="h-100 bg-gray-50 rounded-4 border border-gray-100 p-3">
                    <div className="small text-secondary mb-2">{metric.label}</div>
                    <div className={`fs-4 fw-bold ${metric.valueClassName}`}>{metric.value}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default ProgressCard;
