import React from 'react';

const ChapterCard = ({ title, status, progress, locked, onClick }) => {
  const isCompleted = status === 'Completed';
  const isWeak = status === 'Weak';
  const isLocked = locked;
  
  return (
    <div 
      onClick={onClick}
      className={`bg-white rounded-xl p-4 border border-gray-100 shadow-sm transition-all duration-300 hover-translate-y h-100 d-flex flex-column ${isLocked ? 'opacity-70 grayscale-50 cursor-not-allowed' : 'cursor-pointer'}`}
    >
      <div className="d-flex justify-content-between align-items-start mb-4">
        <h4 className="fw-bold fs-5 text-primary font-bangla lh-sm">{title}</h4>
        {isCompleted && (
          <span className="px-2 py-1 bg-green-100 text-green-700 text-xs fw-bold rounded-3 flex-shrink-0 d-flex align-items-center gap-1">
            ✅ <span className="d-none d-sm-inline">Done</span>
          </span>
        )}
        {isWeak && (
          <span className="px-2 py-1 bg-red-100 text-red-700 text-xs fw-bold rounded-3 flex-shrink-0 d-flex align-items-center gap-1">
            ⚠️ <span className="d-none d-sm-inline">Weak</span>
          </span>
        )}
        {isLocked && (
          <span className="p-1 bg-gray-100 text-gray-500 rounded-3 flex-shrink-0">
            🔒
          </span>
        )}
      </div>

      <div className="mt-auto vstack gap-3">
        {progress !== undefined && (
          <div>
            <div className="d-flex justify-content-between text-xs text-secondary mb-1">
              <span>Progress</span>
              <span>{progress}%</span>
            </div>
            <div className="progress" style={{ height: '0.5rem' }}>
              <div 
                className={`progress-bar transition-all duration-500 ${isWeak ? 'bg-red-400' : 'bg-accent'}`} 
                role="progressbar" 
                style={{ width: `${progress}%` }}
                aria-valuenow={progress} 
                aria-valuemin="0" 
                aria-valuemax="100"
              ></div>
            </div>
          </div>
        )}

        <button 
          disabled={isLocked}
          className={`w-100 py-2 rounded-3 text-xs fw-semibold border transition-colors ${
            isCompleted 
              ? 'bg-gray-50 text-primary border-gray-200 hover:bg-gray-100'
              : isWeak
              ? 'bg-red-50 text-red-600 border-red-100 hover:bg-red-100'
              : isLocked
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed border-0'
              : 'bg-primary text-white hover-bg-gray-800 shadow-sm border-0'
          }`}
        >
          {isCompleted ? 'Revise' : isWeak ? 'Improve Now' : isLocked ? 'Locked' : 'Continue'}
        </button>
      </div>
    </div>
  );
};

export default ChapterCard;
