export const normalizeMasteryTitle = (value) => String(value || '').trim().toLowerCase();

export const fetchMasterySummary = async ({ token }) => {
  const response = await fetch('/api/mastery/summary', {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  const data = await response.json().catch(() => ({}));
  return { response, data };
};

export const findChapterProgress = (summary, chapterName) => {
  const target = normalizeMasteryTitle(chapterName);
  return (Array.isArray(summary?.chapterProgress) ? summary.chapterProgress : []).find((chapter) => (
    normalizeMasteryTitle(chapter?.chapterName) === target
  )) || null;
};

export const getRecommendedLessonNames = (summary) => (
  Array.isArray(summary?.recommendedExam?.lessonNames)
    ? summary.recommendedExam.lessonNames.filter(Boolean)
    : []
);
