import React from 'react';

const ChapterCard = ({ title, status, progress, locked }) => {
  const isCompleted = status === 'Completed';
  const isWeak = status === 'Weak';
  const isLocked = locked;
  
  return (
    <div className={`bg-white rounded-xl p-5 border border-gray-100 shadow-sm transition-all duration-300 hover:shadow-md hover:-translate-y-1 h-full flex flex-col ${isLocked ? 'opacity-70 grayscale-[0.5]' : ''}`}>
      <div className="flex justify-between items-start mb-4">
        <h4 className="font-bold text-lg text-primary font-bangla leading-tight">{title}</h4>
        {isCompleted && (
          <span className="px-2 py-1 bg-green-100 text-green-700 text-xs font-bold rounded-md flex-shrink-0 flex items-center gap-1">
            ✅ <span className="hidden sm:inline">Done</span>
          </span>
        )}
        {isWeak && (
          <span className="px-2 py-1 bg-red-100 text-red-700 text-xs font-bold rounded-md flex-shrink-0 flex items-center gap-1">
            ⚠️ <span className="hidden sm:inline">Weak</span>
          </span>
        )}
        {isLocked && (
          <span className="p-1 bg-gray-100 text-gray-500 rounded-md flex-shrink-0">
            🔒
          </span>
        )}
      </div>

      <div className="mt-auto space-y-4">
        {progress !== undefined && (
          <div>
            <div className="flex justify-between text-xs text-secondary mb-1">
              <span>Progress</span>
              <span>{progress}%</span>
            </div>
            <div className="h-2 w-full bg-gray-100 rounded-full overflow-hidden">
              <div 
                className={`h-full rounded-full transition-all duration-500 ${isWeak ? 'bg-red-400' : 'bg-accent'}`} 
                style={{ width: `${progress}%` }}
              ></div>
            </div>
          </div>
        )}

        <button 
          disabled={isLocked}
          className={`w-full py-2.5 rounded-lg text-sm font-semibold transition-colors ${
            isCompleted 
              ? 'bg-gray-50 text-primary border border-gray-200 hover:bg-gray-100'
              : isWeak
              ? 'bg-red-50 text-red-600 border border-red-100 hover:bg-red-100'
              : isLocked
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-primary text-white hover:bg-gray-800 shadow-sm hover:shadow'
          }`}
        >
          {isCompleted ? 'Revise' : isWeak ? 'Improve Now' : isLocked ? 'Locked' : 'Continue'}
        </button>
      </div>
    </div>
  );
};

export default ChapterCard;
