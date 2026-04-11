import React from 'react';

const OUTCOME_LABELS = [
  ['again', 'Again'],
  ['hard', 'Hard'],
  ['good', 'Good'],
  ['easy', 'Easy'],
];

const TodayRevisionCard = ({
  revision,
  status,
  error,
  onReviewLesson,
  onPractice,
  onRateTask,
}) => {
  const tasks = Array.isArray(revision?.tasks) ? revision.tasks : [];
  const dueCount = Number(revision?.dueCount) || tasks.length;

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 card-hover-effect mb-4">
      <div className="d-flex flex-column flex-lg-row justify-content-between gap-3 mb-4">
        <div>
          <h3 className="text-lg-custom fw-bold text-primary mb-2 d-flex align-items-center gap-2">
            Today&apos;s Revision
          </h3>
          <div className="text-secondary">
            {dueCount > 0
              ? `${dueCount} lesson${dueCount === 1 ? '' : 's'} due from your mastery signals.`
              : 'Nothing is due right now. Keep studying and Photon will schedule reviews automatically.'}
          </div>
        </div>
      </div>

      {status === 'loading' && <div className="text-secondary">Loading your revision queue…</div>}
      {status === 'error' && <div className="text-danger">{error || 'Revision queue could not be loaded.'}</div>}

      {status !== 'loading' && status !== 'error' && tasks.length > 0 && (
        <div className="vstack gap-3">
          {tasks.map((task) => (
            <div key={task.id} className="border border-orange-100 bg-orange-50 rounded-4 p-3">
              <div className="d-flex flex-column flex-lg-row justify-content-between gap-3">
                <div>
                  <div className="fw-bold text-primary font-bangla">{task.lessonName}</div>
                  <div className="small text-secondary font-bangla">{task.chapterName}</div>
                  <div className="small text-secondary mt-2">{task.reason}</div>
                  <div className="small fw-semibold text-primary mt-2">Mastery: {task.masteryScore}%</div>
                </div>

                <div className="d-flex flex-column gap-2" style={{ minWidth: '15rem' }}>
                  <div className="d-flex flex-wrap gap-2">
                    <button
                      type="button"
                      onClick={() => onReviewLesson(task)}
                      className="px-3 py-2 rounded-pill border-0 bg-primary text-white small fw-semibold"
                    >
                      Review Lesson
                    </button>
                    <button
                      type="button"
                      onClick={() => onPractice(task)}
                      className="px-3 py-2 rounded-pill border border-orange-100 bg-white text-primary small fw-semibold"
                    >
                      Practice
                    </button>
                  </div>

                  <div>
                    <div className="small fw-semibold text-secondary text-uppercase mb-2">After reviewing</div>
                    <div className="d-flex flex-wrap gap-2">
                      {OUTCOME_LABELS.map(([outcome, label]) => (
                        <button
                          key={`${task.id}-${outcome}`}
                          type="button"
                          onClick={() => onRateTask(task.id, outcome)}
                          className="px-3 py-1 rounded-pill border border-gray-200 bg-white text-secondary small fw-semibold"
                        >
                          {label}
                        </button>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default TodayRevisionCard;
