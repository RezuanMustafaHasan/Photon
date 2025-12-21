import React from 'react';
import Navbar from '../components/Navbar';
import AISuggestionCard from '../components/AISuggestionCard';
import ProgressCard from '../components/ProgressCard';
import ChapterGrid from '../components/ChapterGrid';

const Dashboard = ({ onChapterClick }) => {
  return (
    <div className="min-h-screen bg-background pb-12">
      <Navbar />
      
      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-8">
        {/* Top Section: AI Suggestion & Progress */}
        <div className="flex flex-col lg:flex-row gap-6">
          {/* AI Suggestion Card (approx 65% width) */}
          <div className="lg:w-[65%]">
            <AISuggestionCard />
          </div>
          
          {/* Progress Card (approx 35% width) */}
          <div className="lg:w-[35%]">
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
