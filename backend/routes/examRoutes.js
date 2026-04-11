import { Router } from 'express';
import authMiddleware from '../middleware/authMiddleware.js';
import { completeExam, generateExam, getExamAttempt, getExamHistory } from '../controllers/examController.js';

const passthrough = (_req, _res, next) => {
  next();
};

export const createExamRouter = ({
  examGenerateLimiter = passthrough,
  examCompleteLimiter = passthrough,
} = {}) => {
  const router = Router();

  router.post('/generate', authMiddleware, examGenerateLimiter, generateExam);
  router.post('/complete', authMiddleware, examCompleteLimiter, completeExam);
  router.get('/history', authMiddleware, getExamHistory);
  router.get('/:attemptId', authMiddleware, getExamAttempt);

  return router;
};

export default createExamRouter;
