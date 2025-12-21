import React from 'react';

const LessonItem = ({ title, isCompleted, isActive }) => {
  return (
    <div 
      className={`flex items-center gap-3 p-3 rounded-lg cursor-pointer transition-all duration-200 group ${
        isActive 
          ? 'bg-orange-50/50' 
          : 'hover:bg-gray-50'
      }`}
    >
      <div className={`flex-shrink-0 ${isCompleted ? 'text-accent' : 'text-gray-300'}`}>
        {isCompleted ? (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-5 h-5">
            <path fillRule="evenodd" d="M2.25 12c0-5.385 4.365-9.75 9.75-9.75s9.75 4.365 9.75 9.75-4.365 9.75-9.75 9.75S2.25 17.385 2.25 12zm13.36-1.814a.75.75 0 10-1.22-.872l-3.236 4.53L9.53 12.22a.75.75 0 00-1.06 1.06l2.25 2.25a.75.75 0 001.14-.094l3.75-5.25z" clipRule="evenodd" />
          </svg>
        ) : (
          <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="w-5 h-5">
            <circle cx="12" cy="12" r="9" />
          </svg>
        )}
      </div>
      <span className={`text-sm font-medium font-bangla ${isActive ? 'text-primary font-bold' : 'text-secondary group-hover:text-primary'}`}>
        {title}
      </span>
    </div>
  );
};

export default LessonItem;
