import React, { useState } from 'react';
import Dashboard from './pages/Dashboard';
import ChapterChat from './pages/ChapterChat';
import LandingPage from './pages/LandingPage';

function App() {
  const [currentView, setCurrentView] = useState('landing');
  const [selectedChapter, setSelectedChapter] = useState(null);

  const navigateToChapter = (chapterTitle) => {
    setSelectedChapter(chapterTitle);
    setCurrentView('chapter-chat');
  };

  const navigateToDashboard = () => {
    setCurrentView('dashboard');
    setSelectedChapter(null);
  };
  
  const handleLogin = () => {
    setCurrentView('dashboard');
  };

  return (
    <>
      {currentView === 'landing' && <LandingPage onLogin={handleLogin} />}
      {currentView === 'dashboard' && <Dashboard onChapterClick={navigateToChapter} />}
      {currentView === 'chapter-chat' && <ChapterChat chapterTitle={selectedChapter} onBack={navigateToDashboard} />}
    </>
  );
}

export default App;
