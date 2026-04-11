import mongoose from 'mongoose';
import UserRevisionTask from '../models/UserRevisionTask.js';
import { getMasterySummary } from './mastery.js';
import { normalizeTitle } from './syllabus.js';

const DAY_IN_MS = 24 * 60 * 60 * 1000;
const DUE_TASK_LIMIT = 5;

const OUTCOME_CONFIG = {
  again: { baseDays: 1, easeDelta: -0.2, source: 'lapse' },
  hard: { baseDays: 2, easeDelta: -0.1, source: 'review' },
  good: { baseDays: 4, easeDelta: 0.05, source: 'review' },
  easy: { baseDays: 7, easeDelta: 0.15, source: 'review' },
};

const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

const asCount = (value) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) && numeric > 0 ? numeric : 0;
};

const buildQuery = ({ userId, chapterName, lessonName }) => ({
  userId: String(userId || '').trim(),
  normalizedChapterName: normalizeTitle(chapterName),
  normalizedLessonName: normalizeTitle(lessonName),
});

const addDays = (date, days) => new Date(date.getTime() + (days * DAY_IN_MS));

const buildCandidateReason = (lesson) => {
  if (asCount(lesson.wrongAnswers) > 1 || asCount(lesson.wrongAnswers) > asCount(lesson.correctAnswers)) {
    return {
      source: 'repeated_wrong',
      reason: 'You missed questions from this lesson, so it is due for review.',
    };
  }
  if (asCount(lesson.chatConfusionCount) > 0) {
    return {
      source: 'chat_confusion',
      reason: 'You asked for clearer explanations here, so revisit it today.',
    };
  }
  if (asCount(lesson.masteryScore) < 40) {
    return {
      source: 'weak_mastery',
      reason: 'Your mastery score is still low for this lesson.',
    };
  }
  return {
    source: 'low_mastery',
    reason: 'You studied this lesson, but it still needs a short review.',
  };
};

const getRevisionCandidates = (summary) => (
  (Array.isArray(summary?.chapterProgress) ? summary.chapterProgress : [])
    .flatMap((chapter) => (
      (Array.isArray(chapter.lessons) ? chapter.lessons : []).map((lesson) => ({
        ...lesson,
        chapterName: chapter.chapterName,
      }))
    ))
    .filter((lesson) => {
      if (!lesson?.chapterName || !lesson?.lessonName || !lesson.hasEvidence) {
        return false;
      }

      return (
        asCount(lesson.masteryScore) < 40
        || asCount(lesson.chatConfusionCount) > 0
        || asCount(lesson.wrongAnswers) > 1
        || asCount(lesson.wrongAnswers) > asCount(lesson.correctAnswers)
        || (asCount(lesson.lessonTimeSeconds) > 0 && asCount(lesson.masteryScore) < 70)
      );
    })
    .map((lesson) => ({
      ...lesson,
      ...buildCandidateReason(lesson),
    }))
);

const formatTask = (task) => ({
  id: String(task._id),
  chapterName: task.chapterName,
  lessonName: task.lessonName,
  masteryScore: Number(task.masteryScore) || 0,
  dueAt: task.dueAt ? new Date(task.dueAt).toISOString() : '',
  reason: task.reason || '',
  reviewCount: Number(task.reviewCount) || 0,
  lapseCount: Number(task.lapseCount) || 0,
});

const getNextIntervalDays = ({ task, outcome, masteryScore }) => {
  const config = OUTCOME_CONFIG[outcome];
  if (!config) {
    return 1;
  }
  if (outcome === 'again') {
    return 1;
  }

  const previousInterval = Math.max(1, Number(task.intervalDays) || 1);
  const easeLevel = clamp((Number(task.easeLevel) || 2.5) + config.easeDelta, 1.3, 3.2);
  const masteryBoost = Number(masteryScore) >= 70 ? 1 : 0;
  const scaledInterval = Math.round(previousInterval * (outcome === 'hard' ? 1.2 : easeLevel));

  return Math.max(config.baseDays, scaledInterval + masteryBoost);
};

export const refreshRevisionTasks = async ({ userId }) => {
  if (mongoose.connection.readyState !== 1) {
    return { refreshedCount: 0 };
  }

  const safeUserId = String(userId || '').trim();
  if (!safeUserId) {
    return { refreshedCount: 0 };
  }

  const summary = await getMasterySummary({ userId: safeUserId });
  const candidates = getRevisionCandidates(summary);
  const now = new Date();
  let refreshedCount = 0;

  for (const candidate of candidates) {
    const query = buildQuery({
      userId: safeUserId,
      chapterName: candidate.chapterName,
      lessonName: candidate.lessonName,
    });
    const existing = await UserRevisionTask.findOne(query);
    const patch = {
      chapterName: candidate.chapterName,
      lessonName: candidate.lessonName,
      normalizedChapterName: query.normalizedChapterName,
      normalizedLessonName: query.normalizedLessonName,
      masteryScore: asCount(candidate.masteryScore),
      source: candidate.source,
      reason: candidate.reason,
      status: 'active',
    };

    if (existing) {
      Object.assign(existing, patch);
      if (!existing.dueAt) {
        existing.dueAt = now;
      }
      await existing.save();
    } else {
      await UserRevisionTask.create({
        userId: safeUserId,
        ...patch,
        dueAt: now,
      });
    }
    refreshedCount += 1;
  }

  return { refreshedCount };
};

export const getTodayRevision = async ({ userId }) => {
  if (mongoose.connection.readyState !== 1) {
    return { tasks: [], dueCount: 0, nextDueAt: '' };
  }

  const safeUserId = String(userId || '').trim();
  if (!safeUserId) {
    return { tasks: [], dueCount: 0, nextDueAt: '' };
  }

  await refreshRevisionTasks({ userId: safeUserId });

  const now = new Date();
  const [dueTasks, dueCount, nextDueTask] = await Promise.all([
    UserRevisionTask.find({
      userId: safeUserId,
      status: 'active',
      dueAt: { $lte: now },
    })
      .sort({ dueAt: 1, masteryScore: 1, updatedAt: -1 })
      .limit(DUE_TASK_LIMIT)
      .lean(),
    UserRevisionTask.countDocuments({
      userId: safeUserId,
      status: 'active',
      dueAt: { $lte: now },
    }),
    UserRevisionTask.findOne({
      userId: safeUserId,
      status: 'active',
      dueAt: { $gt: now },
    }).sort({ dueAt: 1 }).lean(),
  ]);

  return {
    tasks: dueTasks.map(formatTask),
    dueCount,
    nextDueAt: nextDueTask?.dueAt ? new Date(nextDueTask.dueAt).toISOString() : '',
  };
};

export const reviewRevisionTask = async ({ userId, taskId, outcome }) => {
  const safeUserId = String(userId || '').trim();
  const safeOutcome = String(outcome || '').trim().toLowerCase();

  if (!safeUserId || !mongoose.Types.ObjectId.isValid(taskId) || !OUTCOME_CONFIG[safeOutcome]) {
    return null;
  }

  const task = await UserRevisionTask.findOne({
    _id: new mongoose.Types.ObjectId(taskId),
    userId: safeUserId,
    status: 'active',
  });

  if (!task) {
    return null;
  }

  const config = OUTCOME_CONFIG[safeOutcome];
  const now = new Date();
  const intervalDays = getNextIntervalDays({
    task,
    outcome: safeOutcome,
    masteryScore: task.masteryScore,
  });

  task.intervalDays = intervalDays;
  task.easeLevel = clamp((Number(task.easeLevel) || 2.5) + config.easeDelta, 1.3, 3.2);
  task.reviewCount = asCount(task.reviewCount) + 1;
  task.lapseCount = asCount(task.lapseCount) + (safeOutcome === 'again' ? 1 : 0);
  task.lastReviewedAt = now;
  task.dueAt = addDays(now, intervalDays);
  task.source = config.source;

  await task.save();

  return formatTask(task);
};
