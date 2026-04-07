import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Navbar from '../components/Navbar';
import AISuggestionCard from '../components/AISuggestionCard';
import ProgressCard from '../components/ProgressCard';
import ChapterGrid from '../components/ChapterGrid';
import { useAuth } from '../auth/AuthContext.jsx';
import { createRateLimitNotice } from '../utils/rateLimit.js';
import { fetchMasterySummary, getRecommendedLessonNames } from '../utils/mastery.js';

const Dashboard = ({ onChapterClick }) => {
  const navigate = useNavigate();
  const { token, showRateLimitNotice } = useAuth();
  const [summary, setSummary] = useState(null);
  const [status, setStatus] = useState(token ? 'loading' : 'idle');
  const [error, setError] = useState('');

  useEffect(() => {
    let mounted = true;

    const loadSummary = async () => {
      if (!token) {
        setSummary(null);
        setStatus('idle');
        setError('');
        return;
      }

      setStatus('loading');
      setError('');

      try {
        const { response, data } = await fetchMasterySummary({ token });
        if (response.status === 429) {
          if (mounted) {
            setStatus('idle');
          }
          showRateLimitNotice(createRateLimitNotice(
            data,
            response.headers,
            'Too many requests right now. Please wait before loading your mastery summary again.',
          ));
          return;
        }
        if (!response.ok) {
          throw new Error(data.message || 'Failed to load your study summary.');
        }

        if (mounted) {
          setSummary(data);
          setStatus('ready');
        }
      } catch (loadError) {
        if (mounted) {
          setSummary(null);
          setStatus('error');
          setError(loadError.message || 'Failed to load your study summary.');
        }
      }
    };

    loadSummary();

    return () => {
      mounted = false;
    };
  }, [showRateLimitNotice, token]);

  const handleStartRevision = useCallback(() => {
    const chapterName = summary?.nextStep?.chapterName;
    const lessonName = summary?.nextStep?.lessonName;
    if (!chapterName) {
      return;
    }

    if (lessonName) {
      localStorage.setItem(`photon_last_lesson_${chapterName}`, lessonName);
    }
    onChapterClick(chapterName);
  }, [onChapterClick, summary]);

  const handlePracticeWeakTopics = useCallback(() => {
    const chapterName = summary?.recommendedExam?.chapterName;
    const lessonNames = getRecommendedLessonNames(summary);
    if (!chapterName || !lessonNames.length) {
      return;
    }

    navigate(`/exam?chapter=${encodeURIComponent(chapterName)}`, {
      state: {
        recommendedExam: {
          chapterName,
          lessonNames,
        },
      },
    });
  }, [navigate, summary]);

  return (
    <div className="min-h-screen bg-background pb-5">
      <Navbar />

      <main className="container-xl px-4 px-sm-5 py-5">
        <div className="row g-4 mb-4">
          <div className="col-lg-8">
            <AISuggestionCard
              summary={summary}
              status={status}
              error={error}
              onStartRevision={handleStartRevision}
              onPracticeWeakTopics={handlePracticeWeakTopics}
            />
          </div>

          <div className="col-lg-4">
            <ProgressCard summary={summary} status={status} error={error} />
          </div>
        </div>

        <ChapterGrid
          chapters={Array.isArray(summary?.chapterProgress) ? summary.chapterProgress : []}
          status={status}
          error={error}
          onChapterClick={onChapterClick}
        />
      </main>
    </div>
  );
};

export default Dashboard;
