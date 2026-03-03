import { useMemo, useState } from 'react';
import Navbar from '../components/Navbar';
import LessonSidebar from '../components/LessonSidebar';
import ChatWindow from '../components/ChatWindow';

const createInitialMessages = () => ([
  {
    id: crypto.randomUUID(),
    sender: 'ai',
    text: 'Ask your question here.',
  },
]);

const ChapterChat = ({ chapterTitle, onBack }) => {
  const [selectedLesson, setSelectedLesson] = useState('');
  const [messagesByLesson, setMessagesByLesson] = useState({});

  const activeLesson = selectedLesson || 'general';
  const currentMessages = useMemo(() => {
    return messagesByLesson[activeLesson] || createInitialMessages();
  }, [activeLesson, messagesByLesson]);

  const setCurrentMessages = (updater) => {
    setMessagesByLesson((prev) => {
      const previousMessages = prev[activeLesson] || createInitialMessages();
      const nextMessages = typeof updater === 'function' ? updater(previousMessages) : updater;
      return { ...prev, [activeLesson]: nextMessages };
    });
  };

  const handleSelectLesson = (lesson) => {
    const nextLesson = lesson || '';
    setSelectedLesson(nextLesson);
    if (!nextLesson) {
      return;
    }
    setMessagesByLesson((prev) => {
      if (prev[nextLesson]) {
        return prev;
      }
      return { ...prev, [nextLesson]: createInitialMessages() };
    });
  };

  return (
    <div className="vh-100 d-flex flex-column bg-background overflow-hidden">
      <Navbar />
      
      <main className="flex-grow-1 d-flex overflow-hidden position-relative">
        {/* Left Sidebar - Fixed Width & Scrollable */}
        <div className="d-none d-lg-block w-sidebar-lg w-sidebar-xl h-100 flex-shrink-0 border-end border-gray-100 bg-white">
          <LessonSidebar
            chapterTitle={chapterTitle}
            selectedLesson={selectedLesson}
            onSelectLesson={handleSelectLesson}
          />
        </div>
        
        {/* Right Chat Area - Flex Grow & Independent Scroll */}
        <div className="flex-grow-1 h-100 position-relative d-flex flex-column" style={{ minWidth: 0 }}>
           {/* Back Button for Mobile/Tablet */}
           <div className="d-lg-none p-3 border-bottom border-gray-100 bg-white d-flex align-items-center gap-2">
              <button onClick={onBack} className="small fw-medium text-secondary d-flex align-items-center gap-1 border-0 bg-transparent">
                ← Back
              </button>
              <span className="fw-bold text-primary">{chapterTitle || 'Chapter'}</span>
           </div>

           <ChatWindow
             messages={currentMessages}
             setMessages={setCurrentMessages}
             chapterName={chapterTitle}
             lessonName={selectedLesson}
           />
        </div>
      </main>
    </div>
  );
};

export default ChapterChat;
