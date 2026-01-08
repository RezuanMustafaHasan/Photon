import React from 'react';

const ProgressRing = ({ value, size = 100, strokeWidth = 8 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="position-relative d-flex align-items-center justify-content-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="rotate-n90">
        {/* Background circle */}
        <circle
          stroke="#E2E8F0"
          fill="transparent"
          strokeWidth={strokeWidth}
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        {/* Progress circle */}
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

const ProgressCard = () => {
  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 d-flex flex-row align-items-center gap-4 h-100 card-hover-effect">
      <div className="flex-shrink-0">
        <ProgressRing value={80} />
      </div>
      <div className="flex-1 vstack gap-3 w-100">
        <h3 className="text-lg-custom fw-bold text-primary d-flex align-items-center gap-2">
          📈 Your Progress
        </h3>
        <div className="vstack gap-2">
          <div className="d-flex justify-content-between small">
            <span className="text-secondary">Syllabus completed</span>
            <span className="fw-semibold text-primary">80%</span>
          </div>
          <div className="d-flex justify-content-between small">
            <span className="text-secondary">Consistency</span>
            <span className="fw-semibold text-accent">Good</span>
          </div>
          <div className="d-flex justify-content-between small">
            <span className="text-secondary">Weekly streak</span>
            <span className="fw-semibold text-primary">5 days</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProgressCard;
