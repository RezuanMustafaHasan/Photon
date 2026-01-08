import React from 'react';
import Navbar from '../components/Navbar';
import AISuggestionCard from '../components/AISuggestionCard';
import ProgressCard from '../components/ProgressCard';
import ChapterGrid from '../components/ChapterGrid';

const Dashboard = ({ onChapterClick }) => {
  return (
    <div className="min-h-screen bg-background pb-5">
      <Navbar />
      
      <main className="container-xl px-4 px-sm-5 py-5">
        {/* Top Section: AI Suggestion & Progress */}
        <div className="row g-4 mb-4">
          {/* AI Suggestion Card (approx 65% width) */}
          <div className="col-lg-8">
            <AISuggestionCard />
          </div>
          
          {/* Progress Card (approx 35% width) */}
          <div className="col-lg-4">
            <ProgressCard />
          </div>
        </div>

        {/* Chapters Section */}
        <ChapterGrid onChapterClick={onChapterClick} />
      </main>
    </div>
  );
};

export default Dashboard;
