import React from 'react';
import { getRecentLearningItems } from '../utils/mastery.js';

const relativeTimeFormatter = new Intl.RelativeTimeFormat('en', { numeric: 'auto' });
const shortDateFormatter = new Intl.DateTimeFormat('en-US', { month: 'short', day: 'numeric' });

const formatLastStudied = (value) => {
  if (!value) {
    return 'Recently opened';
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return 'Recently opened';
  }

  const diffMs = date.getTime() - Date.now();
  const diffMinutes = Math.round(diffMs / (60 * 1000));

  if (Math.abs(diffMinutes) < 60) {
    return relativeTimeFormatter.format(diffMinutes, 'minute');
  }

  const diffHours = Math.round(diffMs / (60 * 60 * 1000));
  if (Math.abs(diffHours) < 24) {
    return relativeTimeFormatter.format(diffHours, 'hour');
  }

  const diffDays = Math.round(diffMs / (24 * 60 * 60 * 1000));
  if (Math.abs(diffDays) <= 7) {
    return relativeTimeFormatter.format(diffDays, 'day');
  }

  return shortDateFormatter.format(date);
};

const RecentStudyPanel = ({ summary, status, error, onResumeLesson }) => {
  const items = getRecentLearningItems(summary, 15);

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 dashboard-sticky-panel">
      <div className="d-flex flex-column gap-2 mb-4">
        <div className="small fw-semibold text-secondary text-uppercase">Continue Learning</div>
        <h2 className="fs-5 fw-bold text-primary mb-0">What You Studied Recently</h2>
        <div className="text-secondary">
          Your latest 15 lesson visits stay here so you can jump back in without hunting through the page.
        </div>
      </div>

      {status === 'loading' && <div className="text-secondary">Loading your recent learning…</div>}
      {status === 'error' && <div className="text-danger">{error || 'Recent learning could not be loaded.'}</div>}

      {status !== 'loading' && status !== 'error' && items.length === 0 && (
        <div className="bg-orange-50 border border-orange-100 rounded-4 p-4 text-secondary">
          Your recent learning list will appear here after you spend time inside a lesson.
        </div>
      )}

      {status !== 'loading' && status !== 'error' && items.length > 0 && (
        <div className="recent-study-list custom-scrollbar pe-1">
          <div className="vstack gap-3">
            {items.map((item) => (
              <div key={`${item.chapterName}-${item.lessonName}`} className="recent-study-item border border-gray-100 rounded-4 p-3">
                <div className="d-flex flex-column gap-3">
                  <div>
                    <div className="fw-bold text-primary font-bangla">{item.lessonName}</div>
                    <div className="small text-secondary font-bangla">{item.chapterName}</div>
                  </div>

                  <div className="d-flex flex-wrap gap-2">
                    <span className="px-3 py-1 rounded-pill bg-orange-50 border border-orange-100 text-primary small fw-semibold">
                      {formatLastStudied(item.lastStudiedAt)}
                    </span>
                    <span className="px-3 py-1 rounded-pill bg-gray-50 text-secondary small fw-semibold">
                      Mastery {item.masteryScore}%
                    </span>
                  </div>

                  <div className="small text-secondary">
                    {item.reason || 'Resume this lesson from where you left off.'}
                  </div>

                  <div className="d-flex justify-content-end">
                    <button
                      type="button"
                      onClick={() => onResumeLesson && onResumeLesson(item)}
                      className="px-4 py-2 rounded-pill border-0 custom-gradient-btn text-white fw-semibold"
                    >
                      Resume lesson
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default RecentStudyPanel;
