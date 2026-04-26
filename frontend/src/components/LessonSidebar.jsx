import { useEffect, useMemo, useState } from 'react';
import LessonItem from './LessonItem';
import { useAuth } from '../auth/AuthContext.jsx';
import { createRateLimitNotice } from '../utils/rateLimit.js';
import { fetchMasterySummary, findChapterProgress } from '../utils/mastery.js';

const LessonSidebar = ({
  chapterTitle,
  selectedLesson,
  completedLessonNames,
  onSelectLesson,
}) => {
  const { token, showRateLimitNotice } = useAuth();
  const [lessons, setLessons] = useState([]);
  const [status, setStatus] = useState('idle');
  const [error, setError] = useState('');
  const [chapterMastery, setChapterMastery] = useState(null);

  useEffect(() => {
    let mounted = true;

    const loadLessons = async () => {
      if (!chapterTitle) {
        setLessons([]);
        setStatus('idle');
        return;
      }

      setStatus('loading');
      setError('');

      try {
        const response = await fetch(`/api/chapters/${encodeURIComponent(chapterTitle)}/lessons`);
        const data = await response.json().catch(() => ({}));
        if (response.status === 429) {
          if (mounted) {
            setStatus('idle');
          }
          showRateLimitNotice(createRateLimitNotice(
            data,
            response.headers,
            'Too many requests right now. Please wait before loading lessons again.',
          ));
          return;
        }
        if (!response.ok) {
          throw new Error(data.message || 'Failed to load lessons');
        }

        if (mounted) {
          const items = Array.isArray(data.lessons) ? data.lessons : [];
          setLessons(items);
          if (!selectedLesson && items.length && onSelectLesson) {
            const stored = chapterTitle ? localStorage.getItem(`photon_last_lesson_${chapterTitle}`) : '';
            const initial = stored && items.includes(stored) ? stored : items[0];
            onSelectLesson(initial);
          }
          setStatus('ready');
        }
      } catch (err) {
        if (mounted) {
          setError(err.message);
          setStatus('error');
        }
      }
    };

    loadLessons();

    return () => {
      mounted = false;
    };
  }, [chapterTitle, onSelectLesson, selectedLesson, showRateLimitNotice]);

  useEffect(() => {
    let mounted = true;

    const loadMastery = async () => {
      if (!token || !chapterTitle) {
        setChapterMastery(null);
        return;
      }

      try {
        const { response, data } = await fetchMasterySummary({ token });
        if (response.status === 429) {
          showRateLimitNotice(createRateLimitNotice(
            data,
            response.headers,
            'Too many requests right now. Please wait before loading chapter mastery again.',
          ));
          return;
        }
        if (!response.ok) {
          return;
        }

        if (mounted) {
          setChapterMastery(findChapterProgress(data, chapterTitle));
        }
      } catch {
        if (mounted) {
          setChapterMastery(null);
        }
      }
    };

    loadMastery();

    return () => {
      mounted = false;
    };
  }, [chapterTitle, showRateLimitNotice, token]);

  const lessonProgressMap = useMemo(() => (
    new Map(
      (Array.isArray(chapterMastery?.lessons) ? chapterMastery.lessons : []).map((lesson) => [
        lesson.lessonName,
        lesson,
      ]),
    )
  ), [chapterMastery]);

  const completedLessonSet = useMemo(() => {
    if (completedLessonNames instanceof Set) {
      return completedLessonNames;
    }
    return new Set(Array.isArray(completedLessonNames) ? completedLessonNames : []);
  }, [completedLessonNames]);

  const chapterProgressValue = useMemo(() => {
    if (!lessons.length) {
      return Number(chapterMastery?.masteryScore) || 0;
    }

    const total = lessons.reduce((sum, title) => {
      if (completedLessonSet.has(title)) {
        return sum + 100;
      }
      return sum + (Number(lessonProgressMap.get(title)?.masteryScore) || 0);
    }, 0);

    return Math.round(total / lessons.length);
  }, [chapterMastery?.masteryScore, completedLessonSet, lessonProgressMap, lessons]);

  return (
    <div className="h-100 d-flex flex-column bg-white border-end border-gray-100">
      <div className="p-4 border-bottom border-gray-100 bg-white sticky-top z-1">
        <h2 className="fs-5 fw-bold text-primary font-bangla mb-3">{chapterTitle || 'Chapter'}</h2>
        <div className="d-flex align-items-center gap-2">
          <div className="flex-grow-1 bg-gray-100 rounded-pill overflow-hidden" style={{ height: '0.375rem' }}>
            <div className="h-100 bg-accent rounded-pill" style={{ width: `${chapterProgressValue}%` }}></div>
          </div>
          <span className="text-xs fw-bold text-secondary">{chapterProgressValue}%</span>
        </div>
      </div>

      <div className="flex-grow-1 overflow-y-auto p-3 vstack gap-1 custom-scrollbar">
        {status === 'error' && <div className="text-danger px-2">{error}</div>}
        {status === 'loading' && <div className="text-secondary px-2">Loading…</div>}
        {status !== 'loading' && !lessons.length && !error && <div className="text-secondary px-2">No lessons yet</div>}
        {lessons.map((title, index) => {
          const masteryLesson = lessonProgressMap.get(title);
          const isCompleted = completedLessonSet.has(title) || Number(masteryLesson?.masteryScore) >= 80;
          return (
            <LessonItem
              key={`${title}-${index}`}
              title={title}
              isCompleted={isCompleted}
              isActive={title === selectedLesson}
              onClick={() => {
                if (chapterTitle) {
                  localStorage.setItem(`photon_last_lesson_${chapterTitle}`, title);
                }
                onSelectLesson && onSelectLesson(title);
              }}
            />
          );
        })}
      </div>
    </div>
  );
};

export default LessonSidebar;
