import React from 'react';

const ProgressRing = ({ value, size = 100, strokeWidth = 8 }) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (value / 100) * circumference;

  return (
    <div className="relative flex items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="transform -rotate-90">
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
        />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="text-xl font-bold text-primary">{value}%</span>
      </div>
    </div>
  );
};

const ProgressCard = () => {
  return (
    <div className="bg-white rounded-2xl p-6 shadow-sm border border-gray-100 flex flex-row items-center gap-6 h-full hover:shadow-md transition-shadow">
      <div className="flex-shrink-0">
        <ProgressRing value={80} />
      </div>
      <div className="flex-1 space-y-3 w-full">
        <h3 className="text-lg font-bold text-primary flex items-center gap-2">
          📈 Your Progress
        </h3>
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-secondary">Syllabus completed</span>
            <span className="font-semibold text-primary">80%</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-secondary">Consistency</span>
            <span className="font-semibold text-accent">Good</span>
          </div>
          <div className="flex justify-between text-sm">
            <span className="text-secondary">Weekly streak</span>
            <span className="font-semibold text-primary">5 days</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ProgressCard;
