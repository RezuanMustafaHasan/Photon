import { ipKeyGenerator, rateLimit } from 'express-rate-limit';
import { RedisStore } from 'rate-limit-redis';

const noopMiddleware = (_req, _res, next) => {
  next();
};

const toPositiveInteger = (value) => {
  const numeric = Number(value);
  if (!Number.isFinite(numeric) || numeric <= 0) {
    return null;
  }
  return Math.ceil(numeric);
};

const getResetTime = (rateLimitInfo) => {
  if (!rateLimitInfo?.resetTime) {
    return null;
  }

  const resetTime = rateLimitInfo.resetTime instanceof Date
    ? rateLimitInfo.resetTime
    : new Date(rateLimitInfo.resetTime);

  return Number.isNaN(resetTime.getTime()) ? null : resetTime;
};

const createRateLimitHandler = ({ policy, message, windowMs }) => (req, res, _next, options) => {
  const rateLimitInfo = req.rateLimit;
  const resetTime = getResetTime(rateLimitInfo);
  const retryAfterSeconds = resetTime
    ? Math.max(1, Math.ceil((resetTime.getTime() - Date.now()) / 1000))
    : Math.max(1, Math.ceil(windowMs / 1000));

  res.set('Retry-After', String(retryAfterSeconds));
  res.status(options.statusCode).json({
    code: 'rate_limit_exceeded',
    policy,
    message,
    limit: toPositiveInteger(rateLimitInfo?.limit) ?? toPositiveInteger(options.limit),
    remaining: Math.max(0, toPositiveInteger(rateLimitInfo?.remaining) ?? 0),
    retryAfterSeconds,
    resetAt: (resetTime || new Date(Date.now() + retryAfterSeconds * 1000)).toISOString(),
  });
};

const createRedisStore = (redisClient, policy) => {
  if (!redisClient) {
    return undefined;
  }

  return new RedisStore({
    prefix: `rl:${policy}:`,
    sendCommand: (...args) => redisClient.sendCommand(args),
  });
};

const createUserKey = (req) => {
  if (req.userId) {
    return `user:${req.userId}`;
  }
  return `ip:${ipKeyGenerator(req.ip || '')}`;
};

const createLimiter = ({
  enabled,
  redisClient,
  policy,
  windowMs,
  limit,
  message,
  keyGenerator,
}) => {
  if (!enabled) {
    return noopMiddleware;
  }

  return rateLimit({
    windowMs,
    limit,
    standardHeaders: 'draft-8',
    legacyHeaders: false,
    identifier: policy,
    requestPropertyName: 'rateLimit',
    passOnStoreError: false,
    handler: createRateLimitHandler({ policy, message, windowMs }),
    keyGenerator,
    store: createRedisStore(redisClient, policy),
  });
};

export const createRateLimiters = ({ enabled = false, redisClient = null } = {}) => ({
  globalApiLimiter: createLimiter({
    enabled,
    redisClient,
    policy: 'global-api',
    windowMs: 60 * 1000,
    limit: 300,
    message: 'Too many requests right now. Please slow down and try again soon.',
  }),
  chapterReadLimiter: createLimiter({
    enabled,
    redisClient,
    policy: 'chapter-read',
    windowMs: 60 * 1000,
    limit: 20,
    message: 'You are refreshing chapter content too quickly. Please wait a moment before loading it again.',
  }),
  authWriteLimiter: createLimiter({
    enabled,
    redisClient,
    policy: 'auth-write',
    windowMs: 60 * 1000,
    limit: 10,
    message: 'Too many sign-in attempts. Please wait a little before trying again.',
  }),
  chatSendLimiter: createLimiter({
    enabled,
    redisClient,
    policy: 'chat-send',
    windowMs: 60 * 1000,
    limit: 20,
    message: 'You are sending messages too quickly. Please wait a moment before trying again.',
    keyGenerator: createUserKey,
  }),
  chatHistoryLimiter: createLimiter({
    enabled,
    redisClient,
    policy: 'chat-history',
    windowMs: 60 * 1000,
    limit: 60,
    message: 'Chat history is cooling down. Please wait a moment before loading it again.',
    keyGenerator: createUserKey,
  }),
  examGenerateLimiter: createLimiter({
    enabled,
    redisClient,
    policy: 'exam-generate',
    windowMs: 60 * 1000,
    limit: 5,
    message: 'You have requested too many exams. Please wait before generating another one.',
    keyGenerator: createUserKey,
  }),
  examCompleteLimiter: createLimiter({
    enabled,
    redisClient,
    policy: 'exam-complete',
    windowMs: 60 * 1000,
    limit: 10,
    message: 'Too many exam submissions right now. Please wait a moment and try again.',
    keyGenerator: createUserKey,
  }),
});
