import React from 'react';
import LessonItem from './LessonItem';

const LessonSidebar = () => {
  const lessons = [
    { title: 'বলের সংজ্ঞা ও প্রকারভেদ', isCompleted: true },
    { title: 'নিউটনের প্রথম সূত্র', isCompleted: true },
    { title: 'নিউটনের দ্বিতীয় সূত্র', isCompleted: true },
    { title: 'নিউটনের তৃতীয় সূত্র', isCompleted: false, isActive: true },
    { title: 'ঘর্ষণ', isCompleted: false },
    { title: 'বাস্তব জীবনের প্রয়োগ', isCompleted: false },
    { title: 'গাণিতিক সমস্যা ১', isCompleted: false },
    { title: 'গাণিতিক সমস্যা ২', isCompleted: false },
    { title: 'বোর্ড পরীক্ষার প্রশ্ন সমাধান', isCompleted: false },
    { title: 'সৃজনশীল প্রশ্ন অনুশীলন', isCompleted: false },
    { title: 'MCQ প্র্যাকটিস', isCompleted: false },
  ];

  return (
    <div className="h-100 d-flex flex-column bg-white border-end border-gray-100">
      {/* Sidebar Header */}
      <div className="p-4 border-bottom border-gray-100 bg-white sticky-top z-1">
        <h2 className="fs-5 fw-bold text-primary font-bangla mb-3">নিউটনের বলবিদ্যা</h2>
        <div className="d-flex align-items-center gap-2">
          <div className="flex-grow-1 bg-gray-100 rounded-pill overflow-hidden" style={{ height: '0.375rem' }}>
            <div className="h-100 bg-accent rounded-pill" style={{ width: '45%' }}></div>
          </div>
          <span className="text-xs fw-bold text-secondary">45%</span>
        </div>
      </div>

      {/* Lesson List */}
      <div className="flex-grow-1 overflow-y-auto p-3 vstack gap-1 custom-scrollbar">
        {lessons.map((lesson, index) => (
          <LessonItem 
            key={index} 
            title={lesson.title} 
            isCompleted={lesson.isCompleted} 
            isActive={lesson.isActive} 
          />
        ))}
      </div>
    </div>
  );
};

export default LessonSidebar;
