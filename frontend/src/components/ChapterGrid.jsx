import React from 'react';
import ChapterCard from './ChapterCard';

const ChapterGrid = ({ chapters, status, error, onChapterClick }) => {
  const safeChapters = Array.isArray(chapters) ? chapters : [];

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100">
      <div className="d-flex flex-column flex-lg-row justify-content-between align-items-lg-center gap-3 mb-4">
        <div>
          <div className="small fw-semibold text-secondary text-uppercase mb-2">Chapter Access</div>
          <h2 className="fs-4 fw-bold text-primary mb-1">Jump Into Any Chapter</h2>
          <div className="text-secondary">Pick a chapter immediately and Photon will reopen your last lesson there.</div>
        </div>
        {safeChapters.length > 0 && (
          <div className="small fw-medium text-secondary">{safeChapters.length} chapters available</div>
        )}
      </div>

      {status === 'loading' && <div className="text-secondary mb-3">Loading chapter mastery…</div>}
      {status === 'error' && <div className="text-danger mb-3">{error}</div>}
      {status !== 'loading' && status !== 'error' && safeChapters.length === 0 && (
        <div className="text-secondary mb-3">No chapters are available yet.</div>
      )}

      <div className="row row-cols-1 row-cols-sm-2 row-cols-lg-4 row-cols-xl-5 g-4">
        {safeChapters.map((chapter) => (
          <div key={chapter.chapterName} className="col">
            <ChapterCard
              title={chapter.chapterName}
              status={chapter.status}
              progress={chapter.masteryScore}
              onClick={() => onChapterClick(chapter.chapterName)}
            />
          </div>
        ))}
      </div>
    </div>
  );
};

export default ChapterGrid;
