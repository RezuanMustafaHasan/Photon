import mongoose from 'mongoose';
import UserConceptMastery from '../models/UserConceptMastery.js';
import { getSyllabusOutline, normalizeTitle } from './syllabus.js';

const DAY_IN_MS = 24 * 60 * 60 * 1000;
const WEAK_THRESHOLD = 40;
const STRONG_THRESHOLD = 70;
const COMPLETED_THRESHOLD = 80;

const CHAT_CONFUSION_REGEX = /(?:don't understand|do not understand|confused|unclear|explain again|simpler|easy way|বোঝিনি|বুঝি না|বুঝতে পারছি না|আবার বুঝাও|সহজ করে|ক্লিয়ার না)/i;

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const asCount = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : 0;
};

const hasEvidence = (entry) => (
  asCount(entry?.questionAttempts) > 0
  || asCount(entry?.chatConfusionCount) > 0
  || asCount(entry?.lessonTimeSeconds) > 0
);

export const getMasteryStatus = (score, entry) => {
  if (!hasEvidence(entry) && score <= 0) {
    return 'Not started';
  }
  if (score >= COMPLETED_THRESHOLD) {
    return 'Completed';
  }
  if (score >= STRONG_THRESHOLD) {
    return 'Strong';
  }
  if (score >= WEAK_THRESHOLD) {
    return 'Building';
  }
  return 'Weak';
};

export const computeMasteryScore = (entry, now = new Date()) => {
  const questionAttempts = asCount(entry?.questionAttempts);
  const correctAnswers = asCount(entry?.correctAnswers);
  const wrongAnswers = asCount(entry?.wrongAnswers);
  const lessonTimeSeconds = asCount(entry?.lessonTimeSeconds);
  const chatConfusionCount = asCount(entry?.chatConfusionCount);

  const accuracy = questionAttempts > 0 ? clamp(correctAnswers / questionAttempts, 0, 1) : 0;
  const examScore = questionAttempts > 0 ? 20 + (accuracy * 55) : 0;
  const timeScore = Math.min(lessonTimeSeconds / 180, 1) * 15;
  const practiceBonus = Math.min(questionAttempts, 5) * 2;
  const confusionPenalty = Math.min(chatConfusionCount * 4, 12);
  const repeatPenalty = Math.min(Math.max(wrongAnswers - 1, 0) * 5, 15);

  let recencyBonus = 0;
  if (entry?.lastActivityAt) {
    const lastActivityAt = new Date(entry.lastActivityAt);
    if (!Number.isNaN(lastActivityAt.getTime()) && (now.getTime() - lastActivityAt.getTime()) <= (14 * DAY_IN_MS)) {
      recencyBonus = 5;
    }
  }

  return clamp(
    Math.round(examScore + timeScore + practiceBonus + recencyBonus - confusionPenalty - repeatPenalty),
    0,
    100,
  );
};

const buildReason = (entry) => {
  if (asCount(entry?.wrongAnswers) > Math.max(asCount(entry?.correctAnswers), 0)) {
    return 'You missed questions from this lesson recently.';
  }
  if (asCount(entry?.chatConfusionCount) > 0) {
    return 'You asked for clearer explanations here.';
  }
  if (asCount(entry?.lessonTimeSeconds) < 90) {
    return 'You spent only a short time on this lesson so far.';
  }
  return 'This lesson needs more practice to become stable.';
};

const getActionLabel = (entry) => {
  if (!hasEvidence(entry)) {
    return 'Start This Lesson';
  }
  if (entry.masteryScore < WEAK_THRESHOLD) {
    return 'Review Lesson';
  }
  if (entry.masteryScore < COMPLETED_THRESHOLD) {
    return 'Practice This Topic';
  }
  return 'Continue Learning';
};

const buildEntryKey = (chapterName, lessonName) => `${normalizeTitle(chapterName)}::${normalizeTitle(lessonName)}`;

const createQuery = ({ userId, chapterName, lessonName }) => ({
  userId: String(userId || '').trim(),
  normalizedChapterName: normalizeTitle(chapterName),
  normalizedLessonName: normalizeTitle(lessonName),
});

const ensureMasteryDoc = async ({ userId, chapterName, lessonName }) => {
  if (mongoose.connection.readyState !== 1) {
    return null;
  }

  const safeUserId = String(userId || '').trim();
  const safeChapterName = String(chapterName || '').trim();
  const safeLessonName = String(lessonName || '').trim();

  if (!safeUserId || !safeChapterName || !safeLessonName) {
    return null;
  }

  return UserConceptMastery.findOneAndUpdate(
    createQuery({ userId: safeUserId, chapterName: safeChapterName, lessonName: safeLessonName }),
    {
      $setOnInsert: {
        userId: safeUserId,
        chapterName: safeChapterName,
        lessonName: safeLessonName,
        normalizedChapterName: normalizeTitle(safeChapterName),
        normalizedLessonName: normalizeTitle(safeLessonName),
      },
    },
    {
      upsert: true,
      new: true,
      setDefaultsOnInsert: true,
    },
  );
};

const saveWithRecomputedScore = async (doc, now = new Date()) => {
  if (!doc) {
    return null;
  }

  doc.masteryScore = computeMasteryScore(doc, now);
  await doc.save();
  return doc;
};

export const detectChatConfusion = (message) => CHAT_CONFUSION_REGEX.test(String(message || '').trim());

export const recordLessonActivity = async ({ userId, chapterName, lessonName, seconds }) => {
  const safeSeconds = clamp(Math.round(Number(seconds) || 0), 0, 300);
  if (!safeSeconds) {
    return null;
  }

  const doc = await ensureMasteryDoc({ userId, chapterName, lessonName });
  if (!doc) {
    return null;
  }

  const now = new Date();
  doc.lessonTimeSeconds = asCount(doc.lessonTimeSeconds) + safeSeconds;
  doc.lastLessonSeenAt = now;
  doc.lastActivityAt = now;

  return saveWithRecomputedScore(doc, now);
};

export const recordChatConfusion = async ({ userId, chapterName, lessonName, message }) => {
  if (!detectChatConfusion(message)) {
    return false;
  }

  const doc = await ensureMasteryDoc({ userId, chapterName, lessonName });
  if (!doc) {
    return false;
  }

  const now = new Date();
  doc.chatConfusionCount = asCount(doc.chatConfusionCount) + 1;
  doc.lastLessonSeenAt = now;
  doc.lastActivityAt = now;
  await saveWithRecomputedScore(doc, now);
  return true;
};

export const recordExamMastery = async ({ userId, questions, answers }) => {
  const aggregates = new Map();

  (Array.isArray(questions) ? questions : []).forEach((question) => {
    const chapterName = String(question?.chapterName || '').trim();
    const lessonName = String(question?.topicName || '').trim();
    const questionId = String(question?.id || '').trim();

    if (!chapterName || !lessonName || !questionId) {
      return;
    }

    const selectedOptionIndex = Number(answers?.[questionId]);
    const correctOptionIndex = Number(question?.correctOptionIndex);
    if (!Number.isInteger(selectedOptionIndex) || !Number.isInteger(correctOptionIndex)) {
      return;
    }

    const key = buildEntryKey(chapterName, lessonName);
    if (!aggregates.has(key)) {
      aggregates.set(key, {
        chapterName,
        lessonName,
        questionAttempts: 0,
        correctAnswers: 0,
        wrongAnswers: 0,
      });
    }

    const aggregate = aggregates.get(key);
    aggregate.questionAttempts += 1;
    if (selectedOptionIndex === correctOptionIndex) {
      aggregate.correctAnswers += 1;
    } else {
      aggregate.wrongAnswers += 1;
    }
  });

  const now = new Date();
  for (const aggregate of aggregates.values()) {
    const doc = await ensureMasteryDoc({
      userId,
      chapterName: aggregate.chapterName,
      lessonName: aggregate.lessonName,
    });

    if (!doc) {
      continue;
    }

    doc.questionAttempts = asCount(doc.questionAttempts) + aggregate.questionAttempts;
    doc.correctAnswers = asCount(doc.correctAnswers) + aggregate.correctAnswers;
    doc.wrongAnswers = asCount(doc.wrongAnswers) + aggregate.wrongAnswers;
    doc.lastExamAt = now;
    doc.lastActivityAt = now;

    await saveWithRecomputedScore(doc, now);
  }

  return aggregates.size;
};

export const getMasterySummary = async ({ userId }) => {
  const safeUserId = String(userId || '').trim();
  const [syllabus, masteryDocs] = await Promise.all([
    getSyllabusOutline(),
    safeUserId ? UserConceptMastery.find({ userId: safeUserId }).lean() : [],
  ]);

  const masteryByKey = new Map(
    masteryDocs.map((doc) => [
      buildEntryKey(doc.chapterName, doc.lessonName),
      {
        ...doc,
        masteryScore: computeMasteryScore(doc),
      },
    ]),
  );

  const mergedChapters = syllabus.map((chapter) => {
    const mergedLessons = chapter.lessons.map((lesson) => {
      const doc = masteryByKey.get(buildEntryKey(chapter.chapterName, lesson.lessonName));
      const base = {
        chapterName: chapter.chapterName,
        lessonName: lesson.lessonName,
        questionAttempts: asCount(doc?.questionAttempts),
        correctAnswers: asCount(doc?.correctAnswers),
        wrongAnswers: asCount(doc?.wrongAnswers),
        chatConfusionCount: asCount(doc?.chatConfusionCount),
        lessonTimeSeconds: asCount(doc?.lessonTimeSeconds),
        lastActivityAt: doc?.lastActivityAt || null,
        lastExamAt: doc?.lastExamAt || null,
        lastLessonSeenAt: doc?.lastLessonSeenAt || null,
      };
      const masteryScore = computeMasteryScore(base);

      return {
        ...base,
        masteryScore,
        status: getMasteryStatus(masteryScore, base),
        hasEvidence: hasEvidence(base),
      };
    });

    const totalLessons = mergedLessons.length;
    const practicedLessons = mergedLessons.filter((lesson) => lesson.hasEvidence).length;
    const completedLessons = mergedLessons.filter((lesson) => lesson.masteryScore >= COMPLETED_THRESHOLD).length;
    const masteryScore = totalLessons
      ? Math.round(mergedLessons.reduce((sum, lesson) => sum + lesson.masteryScore, 0) / totalLessons)
      : 0;

    return {
      chapterName: chapter.chapterName,
      masteryScore,
      status: getMasteryStatus(masteryScore, { questionAttempts: practicedLessons }),
      totalLessons,
      practicedLessons,
      completedLessons,
      lessons: mergedLessons.map((lesson) => ({
        lessonName: lesson.lessonName,
        masteryScore: lesson.masteryScore,
        status: lesson.status,
        hasEvidence: lesson.hasEvidence,
      })),
    };
  });

  const allLessons = mergedChapters.flatMap((chapter) => chapter.lessons.map((lesson) => ({
    ...lesson,
    chapterName: chapter.chapterName,
  })));

  const overallProgress = allLessons.length
    ? Math.round(allLessons.reduce((sum, lesson) => sum + lesson.masteryScore, 0) / allLessons.length)
    : 0;
  const practicedLessons = allLessons.filter((lesson) => lesson.hasEvidence).length;
  const completedLessons = allLessons.filter((lesson) => lesson.masteryScore >= COMPLETED_THRESHOLD).length;
  const weakLessons = allLessons.filter((lesson) => lesson.hasEvidence && lesson.masteryScore < WEAK_THRESHOLD).length;

  const weakConcepts = allLessons
    .filter((lesson) => lesson.hasEvidence)
    .sort((left, right) => (
      left.masteryScore - right.masteryScore
      || right.wrongAnswers - left.wrongAnswers
      || right.chatConfusionCount - left.chatConfusionCount
      || left.lessonName.localeCompare(right.lessonName)
    ))
    .slice(0, 3)
    .map((lesson) => ({
      chapterName: lesson.chapterName,
      lessonName: lesson.lessonName,
      masteryScore: lesson.masteryScore,
      reason: buildReason(lesson),
    }));

  const weakestLesson = weakConcepts[0] || null;
  const firstUntouchedLesson = allLessons.find((lesson) => !lesson.hasEvidence) || null;
  const nextLesson = weakestLesson
    ? allLessons.find((lesson) => (
      lesson.chapterName === weakestLesson.chapterName
      && lesson.lessonName === weakestLesson.lessonName
    )) || null
    : firstUntouchedLesson;

  const nextStep = nextLesson
    ? {
      chapterName: nextLesson.chapterName,
      lessonName: nextLesson.lessonName,
      masteryScore: nextLesson.masteryScore,
      actionLabel: getActionLabel(nextLesson),
      reason: weakestLesson ? buildReason(nextLesson) : 'You have not practiced this lesson yet.',
    }
    : null;

  let recommendedExam = {
    chapterName: '',
    lessonNames: [],
  };

  if (weakestLesson) {
    const recommendedChapter = mergedChapters.find((chapter) => chapter.chapterName === weakestLesson.chapterName);
    const lessonNames = (recommendedChapter?.lessons || [])
      .filter((lesson) => lesson.hasEvidence)
      .sort((left, right) => left.masteryScore - right.masteryScore)
      .slice(0, 3)
      .map((lesson) => lesson.lessonName);

    recommendedExam = {
      chapterName: weakestLesson.chapterName,
      lessonNames: lessonNames.length ? lessonNames : [weakestLesson.lessonName],
    };
  }

  return {
    overallProgress,
    totalLessons: allLessons.length,
    practicedLessons,
    completedLessons,
    weakLessons,
    weakConcepts,
    nextStep,
    recommendedExam,
    chapterProgress: mergedChapters,
  };
};
