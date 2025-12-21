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
    <div className="h-full flex flex-col bg-white border-r border-gray-100">
      {/* Sidebar Header */}
      <div className="p-6 border-b border-gray-100 bg-white sticky top-0 z-10">
        <h2 className="text-xl font-bold text-primary font-bangla mb-3">নিউটনের বলবিদ্যা</h2>
        <div className="flex items-center gap-2">
          <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div className="h-full bg-accent w-[45%] rounded-full"></div>
          </div>
          <span className="text-xs font-bold text-secondary">45%</span>
        </div>
      </div>

      {/* Lesson List */}
      <div className="flex-1 overflow-y-auto p-4 space-y-1 custom-scrollbar">
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
