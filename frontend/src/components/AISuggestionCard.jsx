import React from 'react';
import { getRecommendedLessonNames } from '../utils/mastery.js';

const AISuggestionCard = ({
  summary,
  status,
  error,
  onStartRevision,
  onPracticeWeakTopics,
}) => {
  const nextStep = summary?.nextStep || null;
  const weakConcepts = Array.isArray(summary?.weakConcepts) ? summary.weakConcepts : [];
  const recommendedLessonNames = getRecommendedLessonNames(summary);
  const hasExamRecommendation = Boolean(summary?.recommendedExam?.chapterName && recommendedLessonNames.length);

  return (
    <div className="bg-white rounded-2xl p-4 shadow-sm border border-gray-100 h-100 d-flex flex-column justify-content-between card-hover-effect">
      <div>
        <h3 className="text-lg-custom fw-bold text-primary mb-4 d-flex align-items-center gap-2">
          📌 Next Step for You
        </h3>

        {status === 'loading' && (
          <div className="vstack gap-3 text-secondary leading-relaxed">
            <p className="mb-0">Photon is building your live mastery summary from your lessons, chat, and exam history.</p>
          </div>
        )}

        {status === 'error' && (
          <div className="vstack gap-3 text-secondary leading-relaxed">
            <p className="mb-0">{error || 'Your study summary could not be loaded right now.'}</p>
          </div>
        )}

        {status !== 'loading' && status !== 'error' && (
          <div className="vstack gap-3 text-secondary leading-relaxed">
            {nextStep ? (
              <>
                <p className="mb-0">
                  Next up: <span className="fw-semibold text-primary font-bangla">{nextStep.lessonName}</span>
                  {' '}from <span className="fw-semibold text-primary font-bangla">{nextStep.chapterName}</span>.
                </p>
                <p className="mb-0">{nextStep.reason}</p>
                <p className="fw-medium text-primary bg-orange-50 p-2 rounded-3 border border-orange-100 mb-0">
                  {nextStep.actionLabel}
                </p>
              </>
            ) : (
              <p className="mb-0">Start your first lesson and Photon will turn your activity into real mastery guidance.</p>
            )}

            {weakConcepts.length > 0 && (
              <div>
                <div className="small fw-semibold text-secondary text-uppercase mb-2">Weak topics to focus on</div>
                <div className="d-flex flex-wrap gap-2">
                  {weakConcepts.map((concept) => (
                    <span
                      key={`${concept.chapterName}-${concept.lessonName}`}
                      className="px-3 py-2 rounded-pill bg-orange-50 border border-orange-100 text-primary small fw-semibold font-bangla"
                    >
                      {concept.lessonName}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="mt-4 d-flex flex-column flex-sm-row gap-2">
        <button
          type="button"
          onClick={onStartRevision}
          disabled={!nextStep}
          className="w-100 w-sm-auto custom-gradient-btn text-white px-4 py-2 rounded-xl fw-semibold d-flex align-items-center justify-content-center gap-2 border-0"
        >
          Start Revision
          <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" viewBox="0 0 20 20" fill="currentColor" style={{ width: '1.25rem', height: '1.25rem' }}>
            <path fillRule="evenodd" d="M10.293 3.293a1 1 0 011.414 0l6 6a1 1 0 010 1.414l-6 6a1 1 0 01-1.414-1.414L14.586 11H3a1 1 0 110-2h11.586l-4.293-4.293a1 1 0 010-1.414z" clipRule="evenodd" />
          </svg>
        </button>

        {hasExamRecommendation && (
          <button
            type="button"
            onClick={onPracticeWeakTopics}
            className="w-100 w-sm-auto px-4 py-2 rounded-xl fw-semibold border border-orange-100 bg-orange-50 text-primary"
          >
            Practice Weak Topics
          </button>
        )}
      </div>
    </div>
  );
};

export default AISuggestionCard;
