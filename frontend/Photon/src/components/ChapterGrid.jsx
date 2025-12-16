import React from 'react';
import ChapterCard from './ChapterCard';

const ChapterGrid = () => {
  const chapters = [
    { title: 'ভেক্টর', status: 'Completed', progress: 100 },
    { title: 'নিউটনের বলবিদ্যা', progress: 45 },
    { title: 'মহাকর্ষ ও অভিকর্ষ', status: 'Weak', progress: 20 },
    { title: 'তরঙ্গ ও দোলন', locked: true },
    { title: 'কাজ, শক্তি ও ক্ষমতা', locked: true },
  ];

  return (
    <div className="mt-10">
      <h2 className="text-xl font-bold text-primary mb-6 flex items-center gap-2">
        📘 HSC Physics Chapters
      </h2>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5 gap-6">
        {chapters.map((chapter, index) => (
          <ChapterCard key={index} {...chapter} />
        ))}
      </div>
    </div>
  );
};

export default ChapterGrid;
