import React from 'react';
import ChapterCard from './ChapterCard';

const ChapterGrid = ({ onChapterClick }) => {
  const chapters = [
    { title: 'ভেক্টর', status: 'Completed', progress: 100 },
    { title: 'নিউটনের বলবিদ্যা', progress: 45 },
    { title: 'মহাকর্ষ ও অভিকর্ষ', status: 'Weak', progress: 20 },
    { title: 'তরঙ্গ ও দোলন', locked: true },
    { title: 'কাজ, শক্তি ও ক্ষমতা', locked: true },
  ];

  return (
    <div className="mt-5">
      <h2 className="fs-5 fw-bold text-primary mb-4 d-flex align-items-center gap-2">
        📘 HSC Physics Chapters
      </h2>
      <div className="row row-cols-1 row-cols-sm-2 row-cols-lg-4 row-cols-xl-5 g-4">
        {chapters.map((chapter, index) => (
          <div key={index} className="col">
            <ChapterCard {...chapter} onClick={() => !chapter.locked && onChapterClick(chapter.title)} />
          </div>
        ))}
      </div>
    </div>
  );
};

export default ChapterGrid;
