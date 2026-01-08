import React, { useState } from 'react';
import Dashboard from './pages/Dashboard';
import ChapterChat from './pages/ChapterChat';

function App() {
  const [currentView, setCurrentView] = useState('dashboard');
  const [selectedChapter, setSelectedChapter] = useState(null);

  const navigateToChapter = (chapterTitle) => {
    setSelectedChapter(chapterTitle);
    setCurrentView('chapter-chat');
  };

  const navigateToDashboard = () => {
    setCurrentView('dashboard');
    setSelectedChapter(null);
  };

  return (
    <>
      {currentView === 'dashboard' && <Dashboard onChapterClick={navigateToChapter} />}
      {currentView === 'chapter-chat' && <ChapterChat chapterTitle={selectedChapter} onBack={navigateToDashboard} />}
    </>
  );
}

export default App;
