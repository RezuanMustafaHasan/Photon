import React from 'react';
import Navbar from '../components/Navbar';
import LessonSidebar from '../components/LessonSidebar';
import ChatWindow from '../components/ChatWindow';

const ChapterChat = ({ chapterTitle, onBack }) => {
  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <Navbar />
      
      <main className="flex-1 flex overflow-hidden relative">
        {/* Left Sidebar - Fixed Width & Scrollable */}
        <div className="hidden lg:block w-[280px] xl:w-[320px] h-full flex-shrink-0 border-r border-gray-100 bg-white">
          <LessonSidebar />
        </div>
        
        {/* Right Chat Area - Flex Grow & Independent Scroll */}
        <div className="flex-1 h-full relative flex flex-col min-w-0">
           {/* Back Button for Mobile/Tablet */}
           <div className="lg:hidden p-4 border-b border-gray-100 bg-white flex items-center gap-2">
              <button onClick={onBack} className="text-sm font-medium text-secondary flex items-center gap-1">
                ← Back
              </button>
              <span className="font-bold text-primary">{chapterTitle || 'Chapter'}</span>
           </div>

           <ChatWindow />
        </div>
      </main>
    </div>
  );
};

export default ChapterChat;
