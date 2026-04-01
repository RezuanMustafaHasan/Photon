import mongoose from 'mongoose';
import ExamAttempt from '../models/ExamAttempt.js';

const FASTAPI_BASE_URL = process.env.FASTAPI_BASE_URL || 'http://localhost:8000';
const FASTAPI_EXAM_URL = `${FASTAPI_BASE_URL}/exam/generate`;
const FASTAPI_ANALYZE_URL = `${FASTAPI_BASE_URL}/exam/analyze`;
const MIN_QUESTION_COUNT = 1;
const MAX_QUESTION_COUNT = 50;

const normalizeTitle = (value) => String(value || '').trim().toLowerCase();

const sanitizeSelections = (rawSelections) => {
  if (!Array.isArray(rawSelections)) {
    return [];
  }

  const chapterMap = new Map();

  for (const rawSelection of rawSelections) {
    const chapterName = String(rawSelection?.chapterName || '').trim();
    if (!chapterName) {
      continue;
    }

    const chapterKey = normalizeTitle(chapterName);
    if (!chapterMap.has(chapterKey)) {
      chapterMap.set(chapterKey, {
        chapterName,
        topicMap: new Map(),
      });
    }

    const target = chapterMap.get(chapterKey);
    const topicNames = Array.isArray(rawSelection?.topicNames) ? rawSelection.topicNames : [];
    for (const rawTopicName of topicNames) {
      const topicName = String(rawTopicName || '').trim();
      if (!topicName) {
        continue;
      }

      const topicKey = normalizeTitle(topicName);
      if (!target.topicMap.has(topicKey)) {
        target.topicMap.set(topicKey, topicName);
      }
    }
  }

  return Array.from(chapterMap.values())
    .map(({ chapterName, topicMap }) => ({
      chapterName,
      topicNames: Array.from(topicMap.values()),
    }))
    .filter((selection) => selection.topicNames.length > 0);
};

const parseUserId = (value) => {
  if (mongoose.Types.ObjectId.isValid(value)) {
    return new mongoose.Types.ObjectId(value);
  }
  return value;
};

const validateQuestionCount = (questionCount) => (
  Number.isInteger(questionCount)
  && questionCount >= MIN_QUESTION_COUNT
  && questionCount <= MAX_QUESTION_COUNT
);

const sanitizeQuestions = (rawQuestions) => {
  if (!Array.isArray(rawQuestions)) {
    return [];
  }

  return rawQuestions.map((rawQuestion, index) => ({
    id: String(rawQuestion?.id || `${index + 1}`).trim(),
    chapterName: String(rawQuestion?.chapterName || '').trim(),
    topicName: String(rawQuestion?.topicName || '').trim(),
    question: String(rawQuestion?.question || '').trim(),
    options: Array.isArray(rawQuestion?.options)
      ? rawQuestion.options.map((option) => String(option || '').trim()).filter(Boolean)
      : [],
    correctOptionIndex: Number(rawQuestion?.correctOptionIndex),
  })).filter((question) => (
    question.id
    && question.question
    && question.options.length === 4
    && Number.isInteger(question.correctOptionIndex)
    && question.correctOptionIndex >= 0
    && question.correctOptionIndex <= 3
  ));
};

const sanitizeAnswers = (rawAnswers) => {
  if (!rawAnswers || typeof rawAnswers !== 'object' || Array.isArray(rawAnswers)) {
    return {};
  }

  return Object.fromEntries(
    Object.entries(rawAnswers)
      .map(([questionId, optionIndex]) => [String(questionId).trim(), Number(optionIndex)])
      .filter(([questionId, optionIndex]) => questionId && Number.isInteger(optionIndex) && optionIndex >= 0 && optionIndex <= 3),
  );
};

const getScoreComment = (percentage) => {
  if (percentage >= 95) return 'Excellent';
  if (percentage >= 90) return 'Very Good';
  if (percentage >= 80) return 'Good';
  return 'Need improvements';
};

const buildWrongQuestions = (questions, answers) => {
  return questions
    .map((question) => {
      const selectedOptionIndex = answers[question.id];
      if (!Number.isInteger(selectedOptionIndex) || selectedOptionIndex === question.correctOptionIndex) {
        return null;
      }

      return {
        id: question.id,
        chapterName: question.chapterName,
        topicName: question.topicName,
        question: question.question,
        options: question.options,
        correctOptionIndex: question.correctOptionIndex,
        selectedOptionIndex,
      };
    })
    .filter(Boolean);
};

const buildFallbackSummary = (scoreComment, wrongQuestions) => {
  const recommendedTopicsMap = new Map();
  wrongQuestions.forEach((question) => {
    const key = `${normalizeTitle(question.chapterName)}::${normalizeTitle(question.topicName)}`;
    if (!recommendedTopicsMap.has(key)) {
      recommendedTopicsMap.set(key, {
        chapterName: question.chapterName,
        topicName: question.topicName,
        reason: 'Review this topic again because at least one question from it was answered incorrectly.',
      });
    }
  });

  return {
    headline: 'Performance analysis is currently unavailable',
    overallComment: `${scoreComment}. Your exam was saved, but AI suggestions could not be generated this time.`,
    weaknesses: wrongQuestions.length
      ? ['Review the questions you got wrong and revisit the related topics listed below.']
      : ['No weaknesses detected in this attempt.'],
    recommendedTopics: Array.from(recommendedTopicsMap.values()),
    studyAdvice: wrongQuestions.length
      ? ['Go through the wrong questions one by one and revise the linked topics before retaking a similar exam.']
      : ['Keep practicing mixed-topic exams to maintain this level.'],
  };
};

const getAttemptChapterNames = (selections) => (
  Array.isArray(selections)
    ? selections
      .map((selection) => String(selection?.chapterName || '').trim())
      .filter(Boolean)
    : []
);

const buildAttemptTitle = (chapterNames) => {
  const names = Array.isArray(chapterNames) ? chapterNames.filter(Boolean) : [];
  if (!names.length) {
    return 'Saved exam';
  }

  if (names.length <= 2) {
    return names.join(', ');
  }

  return `${names.slice(0, 2).join(', ')} + ${names.length - 2} others`;
};

const formatAttemptSummary = (attempt) => {
  const chapterNames = getAttemptChapterNames(attempt.selections);
  return {
    id: attempt._id.toString(),
    title: buildAttemptTitle(chapterNames),
    chapterNames,
    score: attempt.score,
    percentage: attempt.percentage,
    scoreComment: attempt.scoreComment,
    questionCount: attempt.questionCount,
    chapterCount: chapterNames.length,
    topicCount: Array.isArray(attempt.selections)
      ? attempt.selections.reduce((count, selection) => count + ((selection?.topicNames || []).length), 0)
      : 0,
    createdAt: attempt.createdAt,
  };
};

const formatAttemptDetail = (attempt) => ({
  id: attempt._id.toString(),
  userId: String(attempt.userId),
  selections: Array.isArray(attempt.selections) ? attempt.selections : [],
  questionCount: attempt.questionCount,
  questions: Array.isArray(attempt.questions) ? attempt.questions : [],
  answers: attempt.answers instanceof Map ? Object.fromEntries(attempt.answers) : (attempt.answers || {}),
  score: attempt.score,
  percentage: attempt.percentage,
  scoreComment: attempt.scoreComment,
  wrongQuestions: Array.isArray(attempt.wrongQuestions) ? attempt.wrongQuestions : [],
  aiSummary: attempt.aiSummary || null,
  createdAt: attempt.createdAt,
  updatedAt: attempt.updatedAt,
});

export const generateExam = async (req, res) => {
  const questionCount = Number(req.body?.questionCount);
  const selections = sanitizeSelections(req.body?.selections);

  if (!validateQuestionCount(questionCount)) {
    res.status(400).json({ message: `questionCount must be an integer between ${MIN_QUESTION_COUNT} and ${MAX_QUESTION_COUNT}.` });
    return;
  }

  if (!selections.length) {
    res.status(400).json({ message: 'Select at least one chapter topic before generating an exam.' });
    return;
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 120000);

  try {
    const upstream = await fetch(FASTAPI_EXAM_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ selections, questionCount }),
      signal: controller.signal,
    });

    const data = await upstream.json().catch(() => null);
    if (!upstream.ok) {
      const statusCode = upstream.status >= 500 ? 502 : upstream.status;
      res.status(statusCode).json({
        message: data?.detail || data?.message || 'Exam generation failed.',
      });
      return;
    }

    const questions = Array.isArray(data?.questions) ? data.questions : [];
    res.json({ questions });
  } catch {
    res.status(502).json({ message: 'FastAPI exam service is unreachable.' });
  } finally {
    clearTimeout(timeoutId);
  }
};

export const completeExam = async (req, res) => {
  const questionCount = Number(req.body?.questionCount);
  const selections = sanitizeSelections(req.body?.selections);
  const questions = sanitizeQuestions(req.body?.questions);
  const answers = sanitizeAnswers(req.body?.answers);

  if (!validateQuestionCount(questionCount)) {
    res.status(400).json({ message: `questionCount must be an integer between ${MIN_QUESTION_COUNT} and ${MAX_QUESTION_COUNT}.` });
    return;
  }

  if (!selections.length) {
    res.status(400).json({ message: 'At least one selected chapter/topic is required.' });
    return;
  }

  if (!questions.length) {
    res.status(400).json({ message: 'Completed exam questions are required.' });
    return;
  }

  if (Object.keys(answers).length !== questions.length) {
    res.status(400).json({ message: 'All questions must be answered before completing the exam.' });
    return;
  }

  try {
    const score = questions.reduce((total, question) => (
      total + (answers[question.id] === question.correctOptionIndex ? 1 : 0)
    ), 0);
    const percentage = questions.length ? Math.round((score / questions.length) * 100) : 0;
    const scoreComment = getScoreComment(percentage);
    const wrongQuestions = buildWrongQuestions(questions, answers);

    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), 120000);

    let aiSummary = null;
    try {
      const upstream = await fetch(FASTAPI_ANALYZE_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          selections,
          questionCount,
          questions,
          answers,
          score,
          percentage,
          scoreComment,
          wrongQuestions,
        }),
        signal: controller.signal,
      });

      const data = await upstream.json().catch(() => null);
      if (upstream.ok && data?.summary) {
        aiSummary = data.summary;
      }
    } catch {
      aiSummary = null;
    } finally {
      clearTimeout(timeoutId);
    }

    const attempt = await ExamAttempt.create({
      userId: parseUserId(req.userId),
      selections,
      questionCount,
      questions,
      answers,
      score,
      percentage,
      scoreComment,
      wrongQuestions,
      aiSummary: aiSummary || buildFallbackSummary(scoreComment, wrongQuestions),
    });

    res.status(201).json({ attempt: formatAttemptDetail(attempt) });
  } catch {
    res.status(500).json({ message: 'Failed to save completed exam.' });
  }
};

export const getExamHistory = async (req, res) => {
  try {
    const attempts = await ExamAttempt.find({ userId: parseUserId(req.userId) })
      .sort({ createdAt: -1 })
      .lean();

    res.json({ history: attempts.map(formatAttemptSummary) });
  } catch {
    res.status(500).json({ message: 'Failed to load exam history.' });
  }
};

export const getExamAttempt = async (req, res) => {
  const attemptId = String(req.params?.attemptId || '').trim();
  if (!mongoose.Types.ObjectId.isValid(attemptId)) {
    res.status(400).json({ message: 'Invalid exam attempt id.' });
    return;
  }

  try {
    const attempt = await ExamAttempt.findOne({
      _id: new mongoose.Types.ObjectId(attemptId),
      userId: parseUserId(req.userId),
    });

    if (!attempt) {
      res.status(404).json({ message: 'Exam attempt not found.' });
      return;
    }

    res.json({ attempt: formatAttemptDetail(attempt) });
  } catch {
    res.status(500).json({ message: 'Failed to load exam attempt.' });
  }
};
