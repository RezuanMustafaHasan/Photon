import React, { useCallback, useEffect, useState } from 'react';
import Navbar from '../components/Navbar';
import ProgressCard from '../components/ProgressCard';
import ChapterGrid from '../components/ChapterGrid';
import RecentStudyPanel from '../components/RecentStudyPanel';
import { useAuth } from '../auth/AuthContext.jsx';
import { createRateLimitNotice } from '../utils/rateLimit.js';
import { fetchMasterySummary } from '../utils/mastery.js';

const Dashboard = ({ onChapterClick }) => {
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

  const handleResumeLesson = useCallback((lesson) => {
    const chapterName = lesson?.chapterName;
    const lessonName = lesson?.lessonName;
    if (!chapterName) {
      return;
    }

    if (lessonName) {
      localStorage.setItem(`photon_last_lesson_${chapterName}`, lessonName);
    }
    onChapterClick(chapterName);
  }, [onChapterClick]);

  return (
    <div className="min-h-screen bg-background pb-5">
      <Navbar />

      <main className="container-xl px-4 px-sm-5 py-4">
        <div className="mb-4">
          <ProgressCard summary={summary} status={status} error={error} />
        </div>

        <div className="row g-4 align-items-start">
          <div className="col-xl-8">
            <ChapterGrid
              chapters={Array.isArray(summary?.chapterProgress) ? summary.chapterProgress : []}
              status={status}
              error={error}
              onChapterClick={onChapterClick}
            />
          </div>

          <div className="col-xl-4">
            <RecentStudyPanel
              summary={summary}
              status={status}
              error={error}
              onResumeLesson={handleResumeLesson}
            />
          </div>
        </div>
      </main>
    </div>
  );
};

export default Dashboard;
