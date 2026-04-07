import React from 'react';
import ChapterCard from './ChapterCard';

const ChapterGrid = ({ chapters, status, error, onChapterClick }) => {
  const safeChapters = Array.isArray(chapters) ? chapters : [];

  return (
    <div className="mt-5">
      <h2 className="fs-5 fw-bold text-primary mb-4 d-flex align-items-center gap-2">
        📘 HSC Physics Chapters
      </h2>

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
