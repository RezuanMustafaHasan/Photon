import React from 'react';

const LessonItem = ({ title, isCompleted, isActive }) => {
  return (
    <div 
      className={`d-flex align-items-center gap-3 p-3 rounded-3 cursor-pointer transition-all ${
        isActive 
          ? 'bg-orange-50-50' 
          : 'hover-bg-gray-50'
      }`}
      style={{ cursor: 'pointer' }}
    >
      <div className={`flex-shrink-0 ${isCompleted ? 'text-accent' : 'text-gray-300'}`}>
        {isCompleted ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" style={{ width: '1.25rem', height: '1.25rem' }}>
            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ width: '1.25rem', height: '1.25rem' }}>
            <circle cx="12" cy="12" r="9" />
          </svg>
        )}
      </div>
      <span className={`text-sm fw-medium font-bangla ${isActive ? 'text-primary fw-bold' : 'text-secondary'}`}>
        {title}
      </span>
    </div>
  );
};

export default LessonItem;
