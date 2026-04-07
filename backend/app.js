import express from 'express';
import cors from 'cors';
import createAuthRouter from './routes/authRoutes.js';
import createChatRouter from './routes/chatRoutes.js';
import createChapterRouter from './routes/chapterRoutes.js';
import createExamRouter from './routes/examRoutes.js';
import createMasteryRouter from './routes/masteryRoutes.js';
import { createRateLimiters } from './middleware/rateLimiters.js';

const parseTrustProxy = (value) => {
  if (value === undefined || value === null || value === '') {
    return false;
  }

  const normalized = String(value).trim().toLowerCase();
  if (['true', 'yes', 'on'].includes(normalized)) {
    return true;
  }
  if (['false', 'no', 'off'].includes(normalized)) {
    return false;
  }

  const numeric = Number(value);
  if (Number.isFinite(numeric)) {
    return numeric;
  }

  return value;
};

export const createApp = ({ rateLimit = {} } = {}) => {
  const app = express();
  const rateLimitEnabled = rateLimit.enabled ?? (String(process.env.RATE_LIMIT_ENABLED || '').trim().toLowerCase() === 'true');
  const limiters = createRateLimiters({
    enabled: rateLimitEnabled,
    redisClient: rateLimit.redisClient ?? null,
  });

  app.set('trust proxy', parseTrustProxy(process.env.TRUST_PROXY));
  app.use(cors({ origin: true }));
  app.use(express.json());

  app.get('/', (_req, res) => {
    res.send('API is running...');
  });

  app.use('/api', limiters.globalApiLimiter);
  app.use('/api/auth', createAuthRouter({ authWriteLimiter: limiters.authWriteLimiter }));
  app.use('/api/chat', createChatRouter({
    chatSendLimiter: limiters.chatSendLimiter,
    chatHistoryLimiter: limiters.chatHistoryLimiter,
  }));
  app.use('/api/chapters', createChapterRouter({
    chapterReadLimiter: limiters.chapterReadLimiter,
  }));
  app.use('/api/exams', createExamRouter({
    examGenerateLimiter: limiters.examGenerateLimiter,
    examCompleteLimiter: limiters.examCompleteLimiter,
  }));
  app.use('/api/mastery', createMasteryRouter());

  return app;
};

export default createApp;
