export const normalizeMasteryTitle = (value) => String(value || '').trim().toLowerCase();

const toTimestamp = (value) => {
  if (!value) {
    return 0;
  }

  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? 0 : date.getTime();
};

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

export const getRecentLearningItems = (summary, limit = 15) => (
  (Array.isArray(summary?.chapterProgress) ? summary.chapterProgress : [])
    .flatMap((chapter) => (
      (Array.isArray(chapter?.lessons) ? chapter.lessons : []).map((lesson) => {
        const lastStudiedAt = lesson?.lastLessonSeenAt
          || ((Number(lesson?.lessonTimeSeconds) || 0) > 0 ? lesson?.lastActivityAt : '');

        return {
          chapterName: chapter.chapterName,
          lessonName: lesson.lessonName,
          masteryScore: Number(lesson?.masteryScore) || 0,
          lessonTimeSeconds: Number(lesson?.lessonTimeSeconds) || 0,
          lastStudiedAt,
          reason: String(lesson?.reason || '').trim(),
        };
      })
    ))
    .filter((lesson) => lesson.chapterName && lesson.lessonName && lesson.lastStudiedAt)
    .sort((left, right) => (
      toTimestamp(right.lastStudiedAt) - toTimestamp(left.lastStudiedAt)
      || right.lessonTimeSeconds - left.lessonTimeSeconds
      || left.lessonName.localeCompare(right.lessonName)
    ))
    .slice(0, limit)
);
